"""
Controller for verify_user action.

Creates an event of type `core.events.event.VerifyContactInformation`
"""

from typing import Tuple, Dict, Any, Optional

from flask import url_for
from wtforms import Form, BooleanField
from wtforms.validators import InputRequired

from arxiv import status
from arxiv.base import logging
import events
from events.exceptions import InvalidEvent, SaveError

from .util import flow_control

logger = logging.getLogger(__name__) #pylint: disable=C0103

Response = Tuple[Dict[str, Any], int, Dict[str, Any]] #pylint: disable=C0103


@flow_control('ui.user', 'ui.authorship', 'ui.user')
def verify_user(request_params: dict, submission_id: Optional[int]) -> Response:
    """
    Generate a `VerifyContactInformation` event.

    If a submission has not yet been created, the `CreateSubmission` event is
    raised to yield a submission_id.
    """
    form = VerifyUserForm(request_params)
    response_data = {'submission_id': submission_id}

    # Process event if go to next page
    if request_params.get('action') == 'next' and form.validate():
        # TODO: Create a concrete User event from cookie info.
        submitter = events.domain.User(1, email='ian413@cornell.edu',
                                       forename='Ima', surname='Nauthor')

        # Create submission if it does not yet exist
        try:
            if submission_id is None:
                submission, _ = events.save(
                    events.CreateSubmission(creator=submitter)
                )
                submission_id = submission.submission_id
        except SaveError:
            # TODO: review exception raising for 5XX errors.
            return {}, status.HTTP_503_SERVICE_UNAVAILABLE, {}

        try:
            # Create VerifyContactInformation event
            submission, _ = events.save(
                events.VerifyContactInformation(creator=submitter),
                submission_id=submission_id
            )
        except InvalidEvent:
            # TODO: Pass along the errors better
            return {}, status.HTTP_400_BAD_REQUEST, {}
        response_data.update({'submission_id': submission_id})
        return response_data, status.HTTP_303_SEE_OTHER, {}

    # build response form
    response_data.update({'form': form})
    logger.debug(f'verify_user data: {form}')

    return response_data, status.HTTP_200_OK, {}


class VerifyUserForm(Form):
    """Generates form with single checkbox to confirm user information."""

    verify_user = BooleanField(
        'By checking this box, I verify that my user information is correct.',
        [InputRequired('Please confirm your user information')]
    )
