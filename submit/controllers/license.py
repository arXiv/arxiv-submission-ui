"""
Controller for license action.

Creates an event of type `core.events.event.SetLicense`
"""

from http import HTTPStatus as status
from typing import Tuple, Dict, Any

from flask import url_for
from werkzeug import MultiDict
from werkzeug.exceptions import InternalServerError, BadRequest
from wtforms.fields import RadioField
from wtforms.validators import InputRequired

from arxiv.forms import csrf
from arxiv.base import logging
from arxiv.license import LICENSES
from arxiv.users.domain import Session
from arxiv.submission import save, InvalidEvent, SaveError
from arxiv.submission.domain.event import SetLicense
from ..util import load_submission
from .util import validate_command, user_and_client_from_session


logger = logging.getLogger(__name__)  # pylint: disable=C0103

Response = Tuple[Dict[str, Any], int, Dict[str, Any]]  # pylint: disable=C0103


def license(method: str, params: MultiDict, session: Session,
            submission_id: int, **kwargs) -> Response:
    """Convert license form data into a `SetLicense` event."""
    submitter, client = user_and_client_from_session(session)

    logger.debug(f'method: {method}, submission: {submission_id}. {params}')

    # Will raise NotFound if there is no such submission.
    submission, submission_events = load_submission(submission_id)

    if method == 'GET' and submission.license:
        # The form should be prepopulated based on the current state of the
        # submission.
        params['license'] = submission.license.uri

    form = LicenseForm(params)
    response_data = {
        'submission_id': submission_id,
        'form': form,
        'submission': submission
    }

    if method == 'POST':
        if form.validate():
            logger.debug('Form is valid, with data: %s', str(form.data))
            license_uri = form.license.data

            # If already selected, nothing more to do.
            if not submission.license or submission.license.uri != license_uri:
                command = SetLicense(creator=submitter, client=client,
                                     license_uri=license_uri)
                if not validate_command(form, command, submission, 'license'):
                    raise BadRequest(response_data)

                try:
                    # Create SetLicense event
                    submission, _ = save(command, submission_id=submission_id)
                except SaveError as e:
                    raise InternalServerError(response_data) from e
        else:   # Form data were invalid.
            raise BadRequest(response_data)

    if params.get('action') in ['previous', 'save_exit', 'next']:
        return response_data, status.SEE_OTHER, {}
    return response_data, status.OK, {}


class LicenseForm(csrf.CSRFForm):
    """Generate form to select license."""

    LICENSE_CHOICES = [(uri, data['label']) for uri, data in LICENSES.items()
                       if data['is_current']]

    license = RadioField(u'Select a license', choices=LICENSE_CHOICES,
                         validators=[InputRequired('Please select a license')])
