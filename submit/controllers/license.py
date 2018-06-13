"""
Controller for license action.

Creates an event of type `core.events.event.SelectLicense`
"""

from typing import Tuple, Dict, Any

from flask import url_for
from wtforms import Form
from wtforms.fields import RadioField

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
    license = RadioField(u'Select a license', choices=[
        ('http://arxiv.org/licenses/nonexclusive-distrib/1.0/', 
            'arXiv.org perpetual, non-exclusive license to distribute this'
            'article'),
        ('http://creativecommons.org/licenses/by-nc-sa/4.0/',
            'Creative Commons Attribution-Noncommercial-ShareAlike license '
            '(CC BY-NC-SA 4.0)'),
        ('http://creativecommons.org/licenses/by-sa/4.0/',
            'Creative Commons Attribution-ShareAlike license (CC BY-SA 4.0)'),
        ('http://creativecommons.org/licenses/by/4.0/', 
            'Creative Commons Attribution license (CC BY 4.0)'),
        ('http://creativecommons.org/publicdomain/zero/1.0/',
            'Creative Commons Public Domain Declaration (CC0 1.0)'),
        ('',  'None of the above licenses apply')])
