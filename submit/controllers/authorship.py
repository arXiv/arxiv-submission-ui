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


def authorship(request_params: dict, submission_id: int) -> Response:
    """
    Converts the authorship form data and converts it to an
    `AssertAuthorship` event.
    """
    form = AuthorshipForm(request_params)

    # Process event if go to next page
    action = request_params.get('action')
    if action in ['previous', 'save_exit', 'next'] and form.validate():
        # TODO: Create a concrete User event from cookie info.
        submitter = events.domain.User(1, email='ian413@cornell.edu',
                                       forename='Ima', surname='Nauthor')

        # Create AssertAuthorship event
        submission, stack = events.save(
            events.AssertAuthorship(creator=submitter),
            submission_id=submission_id
        )

        # TODO: Fix location header using url_for function
        if action == 'next':
            return {}, status.HTTP_303_SEE_OTHER,\
                {'Location': f'http://127.0.0.1:5000/license'}
        elif action == 'previous':
            return {}, status.HTTP_303_SEE_OTHER,\
                {'Location': f'http://127.0.0.1:5000/{submission_id}/verify_user'}
        elif action == 'save_exit':
            # TODO: correct with user portal page
            return {}, status.HTTP_303_SEE_OTHER,\
                {'Location': f'http://127.0.0.1:5000/'}
            
    
    # build response form
    response_data = dict()
    response_data['form'] = form
    logger.debug(f'verify_user data: {form}')

    return response_data, status.HTTP_200_OK, {}


class AuthorshipForm(Form):
    """Generates form with radio button to confirm authorship information."""
    pass
