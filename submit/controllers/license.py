"""
Controller for license action.

Creates an event of type `core.events.event.SetLicense`
"""

from typing import Tuple, Dict, Any

from werkzeug import MultiDict
from werkzeug.exceptions import InternalServerError
from flask import url_for
from wtforms import Form
from wtforms.fields import RadioField
from wtforms.validators import InputRequired

from arxiv import status
from arxiv.base import logging
from arxiv.license import LICENSES
from arxiv.users.domain import Session
import arxiv.submission as events
from ..util import load_submission
from . import util


logger = logging.getLogger(__name__)  # pylint: disable=C0103

Response = Tuple[Dict[str, Any], int, Dict[str, Any]]  # pylint: disable=C0103


def _data_from_submission(params: MultiDict,
                          submission: events.domain.Submission) -> MultiDict:
    """Update form data based on the current state of the submission."""
    if submission.license:
        params['license'] = submission.license.uri
    return params


@util.flow_control('ui.authorship', 'ui.policy', 'ui.user')
def license(method: str, params: MultiDict, session: Session,
            submission_id: int) -> Response:
    """Convert license form data into a `SetLicense` event."""
    submitter, client = util.user_and_client_from_session(session)

    logger.debug(f'method: {method}, submission: {submission_id}. {params}')

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
                    # Create SetLicense event
                    submission, stack = events.save(  # pylint: disable=W0612
                        events.SetLicense(creator=submitter,
                                             license_uri=license_uri),
                        submission_id=submission_id
                    )
                except events.exceptions.InvalidStack as e:
                    logger.error('Could not ConfirmAuthorship: %s', str(e))
                    form.errors     # Causes the form to initialize errors.
                    form._errors['events'] = [ie.message for ie
                                              in e.event_exceptions]
                    logger.debug('InvalidStack; return bad request')
                    return response_data, status.HTTP_400_BAD_REQUEST, {}
                except events.exceptions.SaveError as e:
                    logger.error('Could not save primary event')
                    raise InternalServerError(
                        'There was a problem saving this operation'
                    ) from e
        else:   # Form data were invalid.
            logger.debug('Invalid form data; return bad request')
            return response_data, status.HTTP_400_BAD_REQUEST, {}
    if params.get('action') in ['previous', 'save_exit', 'next']:
        logger.debug('Redirect to %s', params.get('action'))
        return response_data, status.HTTP_303_SEE_OTHER, {}
    logger.debug('Nothing to do, return 200')
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
