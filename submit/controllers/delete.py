"""Provides controllers used to delete/roll back a submission."""

from flask import url_for
from wtforms import BooleanField, validators
from werkzeug import MultiDict

from arxiv import status
from arxiv.base import logging, alerts
from arxiv.submission import Rollback, save
from arxiv.forms import csrf
from arxiv.users.domain import Session
from .util import Response
from . import util
from ..util import load_submission


class DeleteForm(csrf.CSRFForm):
    """Form for deleting a submission or a revision."""

    confirmed = BooleanField('Confirmed',
                             validators=[validators.DataRequired()])


def delete(method: str, params: MultiDict, session: Session,
           submission_id: int) -> Response:
    """
    Delete a submission, replacement, or other request.

    We never really DELETE-delete anything. The workhorse is
    :class:`.Rollback`. For new submissions, this just makes the submission
    inactive (disappear from user views). For replacements, or other kinds of
    requests that happen after the first version is announced, the submission
    is simply reverted back to the state of the last announcement.

    """
    submission, submission_events = load_submission(submission_id)
    response_data = {
        'submission': submission,
        'submission_id': submission.submission_id,
    }

    if method == 'GET':
        form = DeleteForm()
        response_data.update({'form': form})
        return response_data, status.HTTP_200_OK, {}
    elif method == 'POST':
        form = DeleteForm(params)
        if form.validate() and form.confirmed.data:
            user, client = util.user_and_client_from_session(session)
            try:
                save(Rollback(creator=user, client=client),
                     submission_id=submission_id)
            except Exception as e:
                alerts.flash_failure("Whoops!")
            redirect = url_for('ui.create_submission')
            return {}, status.HTTP_303_SEE_OTHER, {'Location': redirect}
        response_data.update({'form': form})
        return response_data, status.HTTP_400_BAD_REQUEST, {}
