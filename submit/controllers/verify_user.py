"""
Controller for verify_user action.

Creates an event of type `core.events.event.ConfirmContactInformation`
"""

from typing import Tuple, Dict, Any, Optional

from werkzeug import MultiDict
from werkzeug.exceptions import InternalServerError, NotFound
from flask import url_for

from wtforms import BooleanField
from wtforms.validators import InputRequired

from arxiv import status
from arxiv.base import logging
from arxiv.forms import csrf
from arxiv.users.domain import Session
import arxiv.submission as events
from ..domain import SubmissionStage
from ..util import load_submission
from . import util


logger = logging.getLogger(__name__)    # pylint: disable=C0103

Response = Tuple[Dict[str, Any], int, Dict[str, Any]]   # pylint: disable=C0103


def verify(method: str, params: MultiDict, session: Session,
           submission_id: int, **kwargs) -> Response:
    """
    Prompt the user to verify their contact information.

    Generates a `ConfirmContactInformation` event when valid data are POSTed.
    """
    logger.debug(f'method: {method}, submission: {submission_id}. {params}')
    submitter, client = util.user_and_client_from_session(session)

    if submission_id:
        # Will raise NotFound if there is no such submission.
        submission, submission_events = load_submission(submission_id)

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

    # Process event if go to next page.
    if method == 'POST':
        if not form.validate():
            logger.debug(f'Form is invalid: {form.errors}')
        if form.validate() and form.verify_user.data:
            logger.debug(f'Form is valid: {form.verify_user.data}')

            # Now that we have a submission, we can verify the user's contact
            # information.
            logger.debug('Submission ID: %s', str(submission_id))

            # There is no need to do this more than once.
            if not submission.submitter_contact_verified:
                try:    # Create ConfirmContactInformation event
                    submission, _ = events.save(
                        events.ConfirmContactInformation(creator=submitter),
                        submission_id=submission_id
                    )
                except events.exceptions.InvalidStack as e:
                    logger.error('Could not ConfirmContactInformation: %s',
                                 str(e))
                    form.errors     # Causes the form to initialize errors.
                    form._errors['events'] = [ie.message for ie
                                              in e.event_exceptions]
                    return response_data, status.HTTP_400_BAD_REQUEST, {}
                except events.exceptions.SaveError as e:
                    logger.error('Could not save primary event')
                    raise InternalServerError(
                        'There was a problem saving this operation'
                    ) from e

        # Either the form data were invalid, or the user did not check the
        # "verify" box.
        else:
            return response_data, status.HTTP_400_BAD_REQUEST, {}
        response_data.update({
            'submission_id': submission_id,
            'submission': submission,
            'submitter': submitter
        })
        return response_data, status.HTTP_303_SEE_OTHER, {}
    return response_data, status.HTTP_200_OK, {}


class VerifyUserForm(csrf.CSRFForm):
    """Generates form with single checkbox to confirm user information."""

    verify_user = BooleanField(
        'By checking this box, I verify that my user information is correct.',
        [InputRequired('Please confirm your user information')],
    )
