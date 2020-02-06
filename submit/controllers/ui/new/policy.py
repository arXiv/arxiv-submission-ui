"""
Controller for policy action.

Creates an event of type `core.events.event.ConfirmPolicy`
"""
from http import HTTPStatus as status
from typing import Tuple, Dict, Any

from flask import url_for
from werkzeug import MultiDict
from werkzeug.exceptions import InternalServerError, BadRequest
from wtforms import BooleanField
from wtforms.validators import InputRequired

from arxiv.forms import csrf
from arxiv.base import logging
from arxiv.users.domain import Session
from arxiv.submission import save, SaveError
from arxiv.submission.domain.event import ConfirmPolicy

from submit.util import load_submission
from submit.routes.ui.flow_control import ready_for_next, stay_on_this_stage
from submit.controllers.ui.util import validate_command, \
    user_and_client_from_session

Response = Tuple[Dict[str, Any], int, Dict[str, Any]]  # pylint: disable=C0103


def policy(method: str, params: MultiDict, session: Session,
           submission_id: int, **kwargs) -> Response:
    """Convert policy form data into an `ConfirmPolicy` event."""
    submitter, client = user_and_client_from_session(session)
    submission, submission_events = load_submission(submission_id)

    if method == 'GET' and submission.submitter_accepts_policy:
        params['policy'] = 'true'

    form = PolicyForm(params)
    response_data = {
        'submission_id': submission_id,
        'form': form,
        'submission': submission
    }

    if method == 'POST' and form.validate():
        accept_policy = form.policy.data
        if accept_policy and not submission.submitter_accepts_policy:
            command = ConfirmPolicy(creator=submitter, client=client)
            if validate_command(form, command, submission, 'policy'):
                try:
                    submission, _ = save(command, submission_id=submission_id)
                    response_data['submission'] = submission
                    return ready_for_next((response_data, status.OK, {}))
                except SaveError as e:
                    raise InternalServerError(response_data) from e

    return stay_on_this_stage((response_data, status.OK, {}))


class PolicyForm(csrf.CSRFForm):
    """Generate form with checkbox to confirm policy."""

    policy = BooleanField(
        'By checking this box, I agree to the policies listed on this page.',
        [InputRequired('Please check the box to agree to the policies')]
    )
