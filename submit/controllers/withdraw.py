"""Controller for withdrawal requests."""

from typing import Tuple, Dict, Any, Optional

from werkzeug import MultiDict
from werkzeug.exceptions import InternalServerError, NotFound

from flask import url_for, Markup
from wtforms.fields import TextField, TextAreaField, Field, BooleanField
from wtforms.validators import InputRequired, ValidationError, optional, \
    DataRequired

from arxiv import status
from arxiv.base import logging, alerts
from arxiv.forms import csrf
from arxiv.users.domain import Session
import arxiv.submission as events

from ..util import load_submission
from . import util

logger = logging.getLogger(__name__)  # pylint: disable=C0103

Response = Tuple[Dict[str, Any], int, Dict[str, Any]]  # pylint: disable=C0103


class WithdrawalForm(csrf.CSRFForm, util.FieldMixin, util.SubmissionMixin):
    """Submit a withdrawal request."""

    withdrawal_reason = TextAreaField(
        'Reason for withdrawal',
        validators=[DataRequired()],
        description=f'Limit {events.RequestWithdrawal.MAX_LENGTH} characters'
    )
    confirmed = BooleanField('Confirmed',
                             false_values=('false', False, 0, '0', ''))

    def validate_withdrawal_reason(form: csrf.CSRFForm, field: Field) -> None:
        """Validate the reason provided for the withdrawal."""
        if field.data:
            form._validate_event(events.RequestWithdrawal, reason=field.data)


def request_withdrawal(method: str, params: MultiDict, session: Session,
                       submission_id: int, **kwargs) -> Response:
    """Request withdrawal of a paper."""
    submitter, client = util.user_and_client_from_session(session)
    logger.debug(f'method: {method}, submission: {submission_id}. {params}')

    # Will raise NotFound if there is no such submission.
    submission, submission_events = load_submission(submission_id)

    # The submission must be published for this to be a withdrawal request.
    if not submission.published:
        alerts.flash_failure(Markup("Submission must first be published. See "
                                    "<a href='https://arxiv.org/help/withdraw'>"
                                    "the arXiv help pages</a> for details."))
        status_url = url_for('ui.create_submission')
        return {}, status.HTTP_303_SEE_OTHER, {'Location': status_url}

    # The form should be prepopulated based on the current state of the
    # submission.
    if method == 'GET':
        params = MultiDict({})

    params.setdefault("confirmed", False)
    form = WithdrawalForm(params)
    form.submission = submission
    form.creator = submitter
    response_data = {
        'submission_id': submission_id,
        'submission': submission,
        'form': form,
    }

    if method == 'POST':
        # We require the user to confirm that they wish to proceed.
        if not form.validate():
            logger.debug('Invalid form data; return bad request')
            return response_data, status.HTTP_400_BAD_REQUEST, {}

        elif not form.events:
            pass
        elif not form.confirmed.data:
            response_data['require_confirmation'] = True
            logger.debug('Not confirmed')
            return response_data, status.HTTP_200_OK, {}

        # form.events get set by the SubmissionMixin during validation.
        # TODO: that's kind of indirect.
        elif form.events:   # Metadata has changed.
            response_data['require_confirmation'] = True
            logger.debug('Form is valid, with data: %s', str(form.data))
            try:
                # Save the events created during form validation.
                submission, stack = events.save(*form.events,
                                                submission_id=submission_id)
            except events.exceptions.InvalidStack as e:
                logger.error('Could not request withdrawal: %s', str(e))
                form.errors     # Causes the form to initialize errors.
                form._errors['events'] = [
                    ie.message for ie in e.event_exceptions
                ]
                logger.debug('InvalidStack; return bad request')
                return response_data, status.HTTP_400_BAD_REQUEST, {}
            except events.exceptions.SaveError as e:
                logger.error('Could not save metadata event')
                raise InternalServerError(
                    'There was a problem saving this operation'
                ) from e

            # Success! Send user back to the submission page.
            alerts.flash_success("Withdrawal request submitted.")
            status_url = url_for('ui.create_submission')
            return {}, status.HTTP_303_SEE_OTHER, {'Location': status_url}
    logger.debug('Nothing to do, return 200')
    return response_data, status.HTTP_200_OK, {}
