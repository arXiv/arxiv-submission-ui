"""
Controller for license action.

Creates an event of type `core.events.event.SelectLicense`
"""

from typing import Tuple, Dict, Any

from flask import url_for
from wtforms import Form
from wtforms.fields import RadioField
from wtforms.validators import InputRequired

from arxiv import status
from arxiv.base import logging
from arxiv.license import LICENSES
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
        # TODO: Create a concrete User event from cookie info.
        submitter = events.domain.User(1, email='ian413@cornell.edu',
                                       forename='Ima', surname='Nauthor')

        # Create SelectLicense event
        submission, stack = events.save(  # pylint: disable=W0612
            events.SelectLicense(
                creator=submitter,
                license_uri=form.license.data
            ),
            submission_id=submission_id
        )
        return response_data, status.HTTP_303_SEE_OTHER, {}

    # build response form
    response_data.update({'form': form})
    logger.debug(f'verify_user data: {form}')
    return response_data, status.HTTP_200_OK, {}


class LicenseForm(Form):
    """Generate form to select license."""
    license = RadioField(
        u'Select a license',
        choices=[(license, data['label']) 
                    for license, data in LICENSES.items() if data['is_current']]
                + [('',  'None of the above licenses apply')],
        validators=[InputRequired('Please select a license')])
