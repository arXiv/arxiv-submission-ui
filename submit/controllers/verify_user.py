"""
Controller for verify_user action.

Creates an event of type `core.events.event.ConfirmContactInformation`
"""
from http import HTTPStatus as status
from typing import Tuple, Dict, Any, Optional

from flask import url_for
from werkzeug import MultiDict
from werkzeug.exceptions import InternalServerError, NotFound, BadRequest
from wtforms import BooleanField
from wtforms.validators import InputRequired

from arxiv.base import logging
from arxiv.forms import csrf
from arxiv.users.domain import Session
from arxiv.submission import save, SaveError
from arxiv.submission.domain.event import ConfirmContactInformation

from ..util import load_submission
from .util import validate_command, user_and_client_from_session


logger = logging.getLogger(__name__)    # pylint: disable=C0103

Response = Tuple[Dict[str, Any], int, Dict[str, Any]]   # pylint: disable=C0103


def verify(method: str, params: MultiDict, session: Session,
           submission_id: int, **kwargs) -> Response:
    """
    Prompt the user to verify their contact information.

    Generates a `ConfirmContactInformation` event when valid data are POSTed.
    """
    logger.debug(f'method: {method}, submission: {submission_id}. {params}')
    submitter, client = user_and_client_from_session(session)

    # Will raise NotFound if there is no such submission.
    submission, _ = load_submission(submission_id)

    # Initialize the form with the current state of the submission.
    if method == 'GET':
        if submission.submitter_contact_verified:
            params['verify_user'] = 'true'

    form = VerifyUserForm(params)
    response_data = {
        'submission_id': submission_id,
        'form': form,
        'submission': submission,
        'submitter': submitter,
        'user': session.user,   # We want the most up-to-date representation.
    }

    if method == 'POST':
        if not (form.validate() and form.verify_user.data):
            # Either the form data were invalid, or the user did not check the
            # "verify" box.
            raise BadRequest(response_data)

        logger.debug(f'Form is valid: {form.verify_user.data}')

        # Now that we have a submission, we can verify the user's contact
        # information. There is no need to do this more than once.
        if not submission.submitter_contact_verified:
            cmd = ConfirmContactInformation(creator=submitter, client=client)
            if not validate_command(form, cmd, submission, 'verify_user'):
                raise BadRequest(response_data)

            try:
                submission, _ = save(cmd, submission_id=submission_id)
            except SaveError as e:
                raise InternalServerError(response_data) from e
            response_data['submission'] = submission

        return response_data, status.SEE_OTHER, {}
    return response_data, status.OK, {}


class VerifyUserForm(csrf.CSRFForm):
    """Generates form with single checkbox to confirm user information."""

    verify_user = BooleanField(
        'By checking this box, I verify that my user information is correct.',
        [InputRequired('Please confirm your user information')],
    )
