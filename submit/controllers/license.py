"""
Controller for license action.

Creates an event of type `core.events.event.SelectLicense`
"""

from typing import Tuple, Dict, Any

from flask import url_for
from wtforms import Form

from arxiv import status
from arxiv.base import logging
import events
from .util import flow_control

# from arxiv-submission-core.events.event import VerifyContactInformation

logger = logging.getLogger(__name__)  # pylint: disable=C0103

Response = Tuple[Dict[str, Any], int, Dict[str, Any]]  # pylint: disable=C0103


@flow_control('ui.authorship', 'ui.policy', 'ui.user')
def license(request_params: dict, submission_id: int) -> Response:
    """Convert license form data into a `SelectLicense` event."""
    form = LicenseForm(request_params)
    response_data = {'submission_id': submission_id}

    # Process event if go to next page
    action = request_params.get('action')
    if action in ['previous', 'save_exit', 'next'] and form.validate():
        # TODO: Write submission info
        return response_data, status.HTTP_303_SEE_OTHER, {}

    # build response form
    response_data.update({'form': form})
    logger.debug(f'verify_user data: {form}')
    return response_data, status.HTTP_200_OK, {}


class LicenseForm(Form):
    """Generate form to select license."""
