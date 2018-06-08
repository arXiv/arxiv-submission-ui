"
Controller for classification actinos.

Creates an event of type `core.events.event.SetPrimaryClassification`
Creates an event of type `core.events.event.AddSecondaryClassification`
"""
from typing import Tuple, Dict, Any

from flask import url_for
from wtforms import Form

from arxiv import status
from arxiv.base import logging
import events

# from arxiv-submission-core.events.event import VerifyContactInformation

logger = logging.getLogger(__name__)  # pylint: disable=C0103

Response = Tuple[Dict[str, Any], int, Dict[str, Any]]  # pylint: disable=C0103


def classification(request_params: dict, submission_id: int) -> Response:
    """Convert primary classification form data into a 
    `SetPrimaryClassification` event."""
    form = PrimaryClassificationForm(request_params)

    # Process event if go to next page
    action = request_params.get('action')
    if action in ['previous', 'save_exit', 'next'] and form.validate():
        # TODO: Write submission info
        pass


        if action == 'next':
            return {}, status.HTTP_303_SEE_OTHER,\
                {'Location': url_for('ui.classification')}
        elif action == 'previous':
            return {}, status.HTTP_303_SEE_OTHER,\
                {'Location': url_for('ui.license',
                 submission_id=submission_id)}
        elif action == 'save_exit':
            # TODO: correct with user portal page
            return {}, status.HTTP_303_SEE_OTHER,\
                {'Location': url_for('ui.user')}

    # build response form
    response_data = dict()
    response_data['form'] = form
    logger.debug(f'verify_user data: {form}')
    response_data['submission_id'] = submission_id

    return response_data, status.HTTP_200_OK, {}


def crosslist(request_params: dict, submission_id: int) -> Response:
    """Convert secondary classification form data into an 
    `AddSecondaryClassification` event."""
    form = SecondaryClassificationForm(request_params)

    # Process event if go to next page
    action = request_params.get('action')
    if action in ['previous', 'save_exit', 'next'] and form.validate():
        # TODO: Write submission info
        pass


        if action == 'next':
            return {}, status.HTTP_303_SEE_OTHER,\
                {'Location': url_for('ui.classification')}
        elif action == 'previous':
            return {}, status.HTTP_303_SEE_OTHER,\
                {'Location': url_for('ui.license',
                 submission_id=submission_id)}
        elif action == 'save_exit':
            # TODO: correct with user portal page
            return {}, status.HTTP_303_SEE_OTHER,\
                {'Location': url_for('ui.user')}

    # build response form
    response_data = dict()
    response_data['form'] = form
    logger.debug(f'verify_user data: {form}')
    response_data['submission_id'] = submission_id

    return response_data, status.HTTP_200_OK, {}


class PrimaryClassificationForm(Form):
    """Form for primary classification selection"""


class SecondaryClassificationForm(Form):
    """Form for secondary classification selection"""


