"""
Controller for verify_user action.

Creates an event of type `core.events.event.VerifyContactInformation`
"""

from typing import Tuple, Dict, Any, Optional

from wtforms import Form, BooleanField, ValidationError
from wtforms.validators import InputRequired

from arxiv import status
from arxiv.base import logging

# from arxiv-submission-core.events.event import VerifyContactInformation

logger = logging.getLogger(__name__)

Response = Tuple[Dict[str, Any], int, Dict[str, Any]]


def verify_user(request_params: dict) -> Response:
    """Processing for verify user form."""
    form = VerifyUserForm(request_params)

    response_data = dict()
    response_data['form'] = form
    logger.debug(f'verify_user data: {form}')

    if request_params.get('next') == '' and form.validate():
        # TODO: Fix location header using url_for function
        return {}, status.HTTP_303_SEE_OTHER,\
            {'Location': f'http://127.0.0.1:5000/authorship'}

    return response_data, status.HTTP_200_OK, {}


class VerifyUserForm(Form):
    """Generates form with single checkbox to confirm user information."""

    verify_user = BooleanField(
        'By checking this box, I verify that my user information is correct.',
        [InputRequired('Please confirm your user information')]
    )
