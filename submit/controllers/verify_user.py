"""
Controller for verify_user action.

Creates an event of type `core.events.event.VerifyContactInformation`
"""

from typing import Tuple, Dict, Any, Optional

from wtforms import Form, BooleanField
from wtforms.validators import InputRequired

from arxiv import status
from arxiv.base import logging
import events

# from arxiv-submission-core.events.event import VerifyContactInformation

logger = logging.getLogger(__name__)

Response = Tuple[Dict[str, Any], int, Dict[str, Any]]


def verify_user(request_params: dict, submission_id: Optional[int]) -> Response:
    """
    Converts the verify_user form data and converts it to a
    `VerifyContactInfromation` event.

    If a submission has not yet been created, the `CreateSubmission` event is
    raised to yield a submission_id.
    """
    form = VerifyUserForm(request_params)

    # Process event if go to next page
    if request_params.get('next') == '' and form.validate():
        # TODO: Create a concrete User event from cookie info. 
        submitter = events.domain.User(1, email='ian413@cornell.edu',
                                       forename='Ima', surname='Nauthor')

        # Create submission if it does not yet exist
        # TODO: Fix database glue then uncomment:
        if submission_id is None:
            submission, stack = events.save(
                events.CreateSubmission(creator=submitter)
            )
            submission_id = submission.submission_id

        # Create VerifyContactInformation event
        submission, stack = events.save(
            events.VerifyContactInformation(creator=submitter),
            submission_id=submission_id
        )

        # TODO: Fix location header using url_for function
        return {}, status.HTTP_303_SEE_OTHER,\
            {'Location': f'http://127.0.0.1:5000/{submission_id}/authorship'}
    
    # build response form
    response_data = dict()
    response_data['form'] = form
    logger.debug(f'verify_user data: {form}')

    return response_data, status.HTTP_200_OK, {}


class VerifyUserForm(Form):
    """Generates form with single checkbox to confirm user information."""

    verify_user = BooleanField(
        'By checking this box, I verify that my user information is correct.',
        [InputRequired('Please confirm your user information')]
    )
