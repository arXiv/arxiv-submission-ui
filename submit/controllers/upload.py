"""Controllers for upload-related requests."""

from typing import Tuple, Dict, Any, Optional

from werkzeug import MultiDict
from werkzeug.exceptions import InternalServerError, BadRequest,\
    MethodNotAllowed
from werkzeug.datastructures import FileStorage

from wtforms import Form, SelectMultipleField, StringField, BooleanField, \
    widgets, validators
from flask import url_for

from arxiv import status
from arxiv.submission import save
from arxiv.submission.domain import Submission, User, Client
from arxiv.submission.domain.event import SetUploadPackage
from arxiv.submission.exceptions import InvalidStack, SaveError
from arxiv.users.domain import Session
from . import util
from ..util import load_submission
from ..services import filemanager
from ..domain import UploadStatus


Response = Tuple[Dict[str, Any], int, Dict[str, Any]]  # pylint: disable=C0103


def _update_submission(submission: Submission, upload_status: UploadStatus,
                       submitter: User, client: Optional[Client] = None) \
        -> Submission:
    existing_upload = getattr(submission.source_content, 'identifier', None)
    if existing_upload == upload_status.identifier:
        return None
    try:
        submission, stack = save(  # pylint: disable=W0612
            SetUploadPackage(
                creator=submitter,
                identifier=upload_status.identifier,
                checksum=upload_status.checksum,
                size=upload_status.size,
            ),
            submission_id=submission.submission_id
        )
    except InvalidStack as e:   # TODO: get more specific
        raise BadRequest('Whoops') from e
    except SaveError as e:      # TODO: get more specific
        raise InternalServerError('Whoops!') from e
    return submission


def _get_upload(params: MultiDict, session: Session, submission: Submission) \
        -> Response:
    response_data = {
        'submission': submission,
        'submission_id': submission.submission_id
    }
    if submission.source_content is None:
        # Nothing to show; should generate a blank-slate upload screen.
        return response_data, status.HTTP_200_OK, {}
    upload_id = submission.source_content.identifier
    try:
        upload_status, headers = filemanager.get_upload_status(upload_id)
    except filemanager.RequestFailed as e:
        # TODO: handle specific failure cases.
        raise InternalServerError('Whoops') from e
    response_data.update({'status': upload_status})
    return response_data, status.HTTP_200_OK, headers


def _post_new_upload(params: MultiDict, pointer: FileStorage, session: Session,
                     submission: Submission) -> Response:
    submitter, client = util.user_and_client_from_session(session)
    try:
        upload_status, headers = filemanager.upload_package(pointer)
    except filemanager.RequestFailed as e:
        # TODO: handle specific failure cases.
        raise InternalServerError('Whoops') from e
    submission = _update_submission(submission, upload_status, submitter,
                                    client)
    response_data = {
        'status': upload_status,
        'submission': submission,
        'submission_id': submission.submission_id
    }
    return response_data, status.HTTP_200_OK, headers


def _post_new_file(params: MultiDict, pointer: FileStorage, session: Session,
                   submission: Submission) -> Response:
    submitter, client = util.user_and_client_from_session(session)
    upload_id = submission.source_content.identifier
    try:
        upload_status, headers = filemanager.add_file(upload_id, pointer)
    except filemanager.RequestFailed as e:
        # TODO: handle specific failure cases.
        raise InternalServerError('Whoops') from e
    submission = _update_submission(submission, upload_status, submitter,
                                    client)
    response_data = {
        'status': upload_status,
        'submission': submission,
        'submission_id': submission.submission_id
    }
    return response_data, status.HTTP_200_OK, headers


def _post_upload(params: MultiDict, files: MultiDict, session: Session,
                 submission: Submission) -> Response:
    try:    # Make sure that we have a file to work with.
        pointer = files['file']
    except KeyError as e:
        raise BadRequest('No file selected') from e

    if submission.source_content is None:   # New upload package.
        return _post_new_upload(params, pointer, session, submission)
    return _post_new_file(params, pointer, session, submission)


@util.flow_control('ui.cross_list', 'ui.file_process', 'ui.user')
def upload(method: str, params: MultiDict, files: MultiDict, session: Session,
           submission_id: int) -> Response:
    """Handle a file upload request."""
    submission = load_submission(submission_id)
    if method == 'GET':
        return _get_upload(params, session, submission)

    # User is attempting an upload of some kind.
    elif method == 'POST':
        return _post_upload(params, files, session, submission)
    raise MethodNotAllowed('Nope')


def delete(method: str, params: MultiDict, session: Session,
           submission_id: int) -> Response:
    submission = load_submission(submission_id)
    upload_id = submission.source_content.identifier
    response_data = {
        'submission': submission,
        'submission_id': submission.submission_id
    }
    if method == 'GET':
        form = DeleteFileForm(MultiDict({'file_path': params['file_path']}))
        response_data.update({'form': form})
        return response_data, status.HTTP_200_OK, {}
    elif method == 'POST':
        form = DeleteFileForm(params)
        if form.validate() and form.confirmed.data:
            filemanager.delete_file(upload_id, form.file_path)
            redirect = url_for('ui.upload_files', submission_id=submission_id)
            return {}, status.HTTP_303_SEE_OTHER, {'Location': redirect}
        response_data.update({'form': form})
        return response_data, status.HTTP_400_BAD_REQUEST, {}


class DeleteFileForm(Form):
    """Form for deleting individual files."""

    file_path = StringField('File', validators=[validators.DataRequired()])
    confirmed = BooleanField('Confirmed',
                             validators=[validators.DataRequired()])
