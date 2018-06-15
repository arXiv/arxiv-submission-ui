"""
Controller for license action.

Creates an event of type `core.events.event.SelectLicense`
"""

from typing import Tuple, Dict, Any

from werkzeug import MultiDict
from flask import url_for
from wtforms import Form
from wtforms.fields import RadioField
from wtforms.validators import InputRequired

from arxiv import status
from arxiv.base import logging
from arxiv.license import LICENSES
import events
from .util import flow_control, load_submission

# from arxiv-submission-core.events.event import VerifyContactInformation

logger = logging.getLogger(__name__)  # pylint: disable=C0103

Response = Tuple[Dict[str, Any], int, Dict[str, Any]]  # pylint: disable=C0103


def _data_from_submission(params: MultiDict,
                          submission: events.domain.Submission) -> MultiDict:
    """Update form data based on the current state of the submission."""
    if submission.license:
        params['license'] = submission.license.uri
    return params


@flow_control('ui.authorship', 'ui.policy', 'ui.user')
def license(method: str, params: MultiDict, submission_id: int) -> Response:
    """Convert license form data into a `SelectLicense` event."""
    logger.debug(f'method: {method}, submission: {submission_id}. {params}')

    # TODO: Create a concrete User from cookie info.
    submitter = events.domain.User(1, email='ian413@cornell.edu',
                                   forename='Ima', surname='Nauthor')

    # Will raise NotFound if there is no such submission.
    submission = load_submission(submission_id)

    # The form should be prepopulated based on the current state of the
    # submission.
    if method == 'GET':
        params = _data_from_submission(params, submission)

    form = LicenseForm(params)
    response_data = {'submission_id': submission_id, 'form': form}

    if method == 'POST':
        if form.validate():
            logger.debug('Form is valid, with data: %s', str(form.data))
            license_uri = form.license.data

            # If already selected, nothing more to do.
            if not submission.license or submission.license.uri != license_uri:
                try:
                    # Create SelectLicense event
                    submission, stack = events.save(  # pylint: disable=W0612
                        events.SelectLicense(creator=submitter,
                                             license_uri=license_uri),
                        submission_id=submission_id
                    )
                except events.exceptions.InvalidStack as e:
                    logger.error('Could not AssertAuthorship: %s', str(e))
                    form.errors     # Causes the form to initialize errors.
                    form._errors['events'] = [ie.message for ie
                                              in e.event_exceptions]
                    return response_data, status.HTTP_400_BAD_REQUEST, {}
                if params.get('action') in ['previous', 'save_exit', 'next']:
                    return response_data, status.HTTP_303_SEE_OTHER, {}
        else:   # Form data were invalid.
            return response_data, status.HTTP_400_BAD_REQUEST, {}

    return response_data, status.HTTP_200_OK, {}


class LicenseForm(Form):
    """Generate form to select license."""

    LICENSE_CHOICES = [(uri, data['label']) for uri, data in LICENSES.items()
                       if data['is_current']] \
        + [('',  'None of the above licenses apply')]

    license = RadioField(
        u'Select a license',
        choices=LICENSE_CHOICES,
        validators=[InputRequired('Please select a license')]
    )
