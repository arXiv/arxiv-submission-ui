"""
Controller for policy action.

Creates an event of type `core.events.event.ConfirmPolicy`
"""

from typing import Tuple, Dict, Any

from werkzeug import MultiDict
from werkzeug.exceptions import InternalServerError
from flask import url_for
from wtforms import BooleanField
from wtforms.validators import InputRequired

from arxiv import status
from arxiv.forms import csrf
from arxiv.base import logging
from arxiv.users.domain import Session
import arxiv.submission as events
from ..domain import SubmissionStage
from ..util import load_submission
from . import util

logger = logging.getLogger(__name__)  # pylint: disable=C0103

Response = Tuple[Dict[str, Any], int, Dict[str, Any]]  # pylint: disable=C0103


def policy(method: str, params: MultiDict, session: Session,
           submission_id: int) -> Response:
    """Convert policy form data into an `ConfirmPolicy` event."""
    submitter, client = util.user_and_client_from_session(session)

    logger.debug(f'method: {method}, submission: {submission_id}. {params}')
    submission, submission_events = load_submission(submission_id)

    if method == 'GET' and submission.submitter_accepts_policy:
        params['policy'] = 'true'

    form = PolicyForm(params)
    response_data = {
        'submission_id': submission_id,
        'form': form,
        'submission': submission
    }

    if method == 'POST':
        if form.validate():
            logger.debug('Form is valid, with data: %s', str(form.data))
            accept_policy = form.policy.data
            if accept_policy and not submission.submitter_accepts_policy:
                try:
                    # Create ConfirmPolicy event
                    submission, stack = events.save(  # pylint: disable=W0612
                        events.ConfirmPolicy(creator=submitter),
                        submission_id=submission_id
                    )
                except events.exceptions.InvalidStack as e:
                    logger.error('Could not ConfirmAuthorship: %s', str(e))
                    form.errors     # Causes the form to initialize errors.
                    form._errors['events'] = [ie.message for ie
                                              in e.event_exceptions]
                    return response_data, status.HTTP_400_BAD_REQUEST, {}
                except events.exceptions.SaveError as e:
                    logger.error('Could not save primary event')
                    raise InternalServerError(
                        'There was a problem saving this operation'
                    ) from e
            if params.get('action') in ['previous', 'save_exit', 'next']:
                return response_data, status.HTTP_303_SEE_OTHER, {}
        else:   # Form data were invalid.
            return response_data, status.HTTP_400_BAD_REQUEST, {}

    return response_data, status.HTTP_200_OK, {}


class PolicyForm(csrf.CSRFForm):
    """Generate form with checkbox to confirm policy."""

    policy = BooleanField(
        'By checking this box, I agree to the policies listed on this page.',
        [InputRequired('Please check the box to agree to the policies')]
    )
