"""
Provides the final preview and confirmation step.
"""

from typing import Tuple, Dict, Any

from werkzeug import MultiDict
from werkzeug.exceptions import InternalServerError, BadRequest
from flask import url_for
from wtforms import BooleanField
from wtforms.validators import InputRequired

from http import HTTPStatus as status
from arxiv.forms import csrf
from arxiv.base import logging
from arxiv.users.domain import Session
from arxiv.submission import save
from arxiv.submission.domain.event import FinalizeSubmission
from arxiv.submission.exceptions import SaveError
from ..util import load_submission
from .util import validate_command, user_and_client_from_session

logger = logging.getLogger(__name__)  # pylint: disable=C0103

Response = Tuple[Dict[str, Any], int, Dict[str, Any]]  # pylint: disable=C0103


def finalize(method: str, params: MultiDict, session: Session,
             submission_id: int, **kwargs) -> Response:
    submitter, client = user_and_client_from_session(session)

    logger.debug(f'method: {method}, submission: {submission_id}. {params}')
    submission, submission_events = load_submission(submission_id)

    form = FinalizationForm(params)

    # The abs preview macro expects a specific struct for submission history.
    submission_history = [{'submitted_date': s.created, 'version': s.version}
                          for s in submission.versions]
    response_data = {
        'submission_id': submission_id,
        'form': form,
        'submission': submission,
        'submission_history': submission_history
    }

    if method == 'POST':
        if form.validate():
            logger.debug('Form is valid, with data: %s', str(form.data))
            proofread_confirmed = form.proceed.data
            if proofread_confirmed:
                command = FinalizeSubmission(creator=submitter)
                if not validate_command(form, command, submission):
                    raise BadRequest(response_data)

                try:
                    # Create ConfirmPolicy event
                    submission, stack = save(  # pylint: disable=W0612
                        command,
                        submission_id=submission_id
                    )
                except SaveError as e:
                    logger.error('Could not save primary event')
                    raise InternalServerError(response_data) from e
            if params.get('action') in ['previous', 'save_exit', 'next']:
                return response_data, status.SEE_OTHER, {}
        else:   # Form data were invalid.
            raise BadRequest(response_data)

    return response_data, status.OK, {}


class FinalizationForm(csrf.CSRFForm):
    """Make sure the user is really really really ready to submit."""

    proceed = BooleanField(
        'By checking this box, I confirm that I have reviewed my submission as'
        ' it will appear on arXiv.',
        [InputRequired('Please confirm that the submission is ready')]
    )


def confirm(method: str, params: MultiDict, session: Session,
            submission_id: int, **kwargs) -> Response:
    submission, submission_events = load_submission(submission_id)
    response_data = {
        'submission_id': submission_id,
        'submission': submission
    }
    return response_data, status.OK, {}
