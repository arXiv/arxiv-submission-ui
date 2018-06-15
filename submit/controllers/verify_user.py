"""
Controller for verify_user action.

Creates an event of type `core.events.event.VerifyContactInformation`
"""

from typing import Tuple, Dict, Any, Optional

from werkzeug.exceptions import InternalServerError
from flask import url_for
from wtforms import Form, BooleanField
from wtforms.validators import InputRequired

from arxiv import status
from arxiv.base import logging
import events

from .util import flow_control

logger = logging.getLogger(__name__)    #pylint: disable=C0103

Response = Tuple[Dict[str, Any], int, Dict[str, Any]]    #pylint: disable=C0103


@flow_control('ui.user', 'ui.authorship', 'ui.user')
def verify_user(method: str, params: dict,
                submission_id: Optional[int] = None) -> Response:
    """
    Prompt the user to verify their contact information.

    Generates a `VerifyContactInformation` event when valid data are POSTed.

    If a submission has not yet been created, the `CreateSubmission` event is
    raised to yield a submission_id.
    """
    logger.debug(f'method: {method}, submission: {submission_id}. {params}')
    form = VerifyUserForm(params)
    response_data = {'submission_id': submission_id, 'form': form}

    # Process event if go to next page.
    if method == 'POST':
        if form.validate() and form.verify_user.data:
            logger.debug(f'Form is valid: {form.verify_user.data}')
            # TODO: Create a concrete User from cookie info.
            submitter = events.domain.User(1, email='ian413@cornell.edu',
                                           forename='Ima', surname='Nauthor')

            # Create submission if it does not yet exist.
            if submission_id is None:
                logger.debug('No submission ID; creating a new submission')
                try:
                    submission, _ = events.save(
                        events.CreateSubmission(creator=submitter)
                    )
                    submission_id = submission.submission_id
                except events.exceptions.InvalidStack as e:
                    logger.error('Could not create submission: %s', e)
                    # Creation requires basically no information, so this is
                    # likely unrecoverable.
                    raise InternalServerError('Creation failed') from e

            # Now that we have a submission, we can verify the user's contact
            # information.
            logger.debug('Submission ID: %s', str(submission_id))
            try:    # Create VerifyContactInformation event
                submission, _ = events.save(
                    events.VerifyContactInformation(creator=submitter),
                    submission_id=submission_id
                )
            except events.exceptions.InvalidStack as e:
                logger.error('Could not perform VerifyContactInformation: %s',
                             str(e))
                form.errors     # Causes the form to initialize errors.
                form._errors['events'] = [ie.message for ie
                                          in e.event_exceptions]
                return response_data, status.HTTP_400_BAD_REQUEST, {}

        # Either the form data were invalid, or the user did not check the
        # "verify" box.
        else:
            return response_data, status.HTTP_400_BAD_REQUEST, {}
        response_data.update({'submission_id': submission_id})
        return response_data, status.HTTP_303_SEE_OTHER, {}
    return response_data, status.HTTP_200_OK, {}


class VerifyUserForm(Form):
    """Generates form with single checkbox to confirm user information."""

    verify_user = BooleanField(
        'By checking this box, I verify that my user information is correct.',
        [InputRequired('Please confirm your user information')]
    )
