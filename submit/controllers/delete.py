"""Provides controllers used to delete/roll back a submission."""

from flask import url_for
from wtforms import BooleanField, validators
from werkzeug import MultiDict
from werkzeug.exceptions import BadRequest, InternalServerError

from http import HTTPStatus as status
from arxiv.base import logging, alerts
from arxiv.submission import Rollback, save
from arxiv.forms import csrf
from arxiv.users.domain import Session
from .util import Response, user_and_client_from_session, validate_command
from ..util import load_submission


class DeleteForm(csrf.CSRFForm):
    """Form for deleting a submission or a revision."""

    confirmed = BooleanField('Confirmed',
                             validators=[validators.DataRequired()])


def delete(method: str, params: MultiDict, session: Session,
           submission_id: int, **kwargs) -> Response:
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
        return response_data, status.OK, {}
    elif method == 'POST':
        form = DeleteForm(params)
        response_data.update({'form': form})
        if form.validate() and form.confirmed.data:
            user, client = user_and_client_from_session(session)
            command = Rollback(creator=user, client=client)
            if not validate_command(form, command, submission, 'confirmed'):
                raise BadRequest(response_data)

            try:
                save(command, submission_id=submission_id)
            except Exception as e:
                alerts.flash_failure("Whoops!")
                raise InternalServerError(response_data) from e
            redirect = url_for('ui.create_submission')
            return {}, status.SEE_OTHER, {'Location': redirect}
        response_data.update({'form': form})
        raise BadRequest(response_data)
