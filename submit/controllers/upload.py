"""
Controllers for upload-related requests.

Things that still need to be done:

- Display error alerts from the file management service.
- Show warnings/errors for individual files in the table. We may need to
  extend the flashing mechanism to "flash" data to the next page (without
  displaying it as a notification to the user).

"""

from typing import Tuple, Dict, Any, Optional

from werkzeug import MultiDict
from werkzeug.exceptions import InternalServerError, BadRequest,\
    MethodNotAllowed
from werkzeug.datastructures import FileStorage

from wtforms import BooleanField, widgets, validators, HiddenField, FileField
from flask import url_for, Markup

from arxiv import status
from arxiv.submission import save
from arxiv.base import logging, alerts
from arxiv.forms import csrf
from arxiv.submission.domain import Submission, User, Client
from arxiv.submission.domain.event import SetUploadPackage
from arxiv.submission.exceptions import InvalidStack, SaveError
from arxiv.users.domain import Session
from . import util
from ..util import load_submission
from ..services import filemanager
from ..domain import Upload, SubmissionStage

logger = logging.getLogger(__name__)

Response = Tuple[Dict[str, Any], int, Dict[str, Any]]  # pylint: disable=C0103

PLEASE_CONTACT_SUPPORT = Markup(
    'If you continue to experience problems, please contact'
    ' <a href="mailto:help@arxiv.org"> arXiv support</a>.'
)


def tidy_filesize(size) -> str:
    """
    Convert upload size to human readable form.

    Decision to use powers of 10 rather than powers of 2 to stay compatible
    with Jinja filesizeformat filter with binary=false setting that we are
    using in file_upload template.

    Parameter: size in bytes
    Returns: formatted string of size in units up through GB

    """
    units = ["B", "KB", "MB", "GB"]
    if size == 0:
        return "0B"
    if size > 1000000000:
        return '{} {}'.format(size, units[3])
    units_index = 0
    while size > 1000:
        units_index += 1
        size = round(size / 1000, 3)
    return '{} {}'.format(size, units[units_index])


def upload_files(method: str, params: MultiDict, files: MultiDict,
                 session: Session, submission_id: int, token: str) -> Response:
    """
    Handle a file upload request.

    GET requests are treated as a request for information about the current
    state of the submission upload.

    POST requests are treated either as package upload or a request to replace
    a file. If a submission upload workspace does not already exist, the upload
    is treated as the former.

    Parameters
    ----------
    method : str
        ``GET`` or ``POST``
    params : :class:`MultiDict`
        The form data from the request.
    files : :class:`MultiDict`
        File data in the multipart request. Values should be
        :class:`FileStorage` instances.
    session : :class:`Session`
        The authenticated session for the request.
    submission_id : int
        The identifier of the submission for which the upload is being made.
    token : str
        The original (encrypted) auth token on the request. Used to perform
        subrequests to the file management service.

    Returns
    -------
    dict
        Response data, to render in template.
    int
        HTTP status code. This should be ``200`` or ``303``, unless something
        goes wrong.
    dict
        Extra headers to add/update on the response. This should include
        the `Location` header for use in the 303 redirect response, if
        applicable.

    """
    logger.debug('%s upload request for submission %i', method, submission_id)
    submission, submission_events = load_submission(submission_id)
    logger.debug('Loaded submission with ID %i', submission.submission_id)

    filemanager.set_auth_token(token)
    if method == 'GET':
        return _get_upload(params, session, submission)

    # User is attempting an upload of some kind.
    elif method == 'POST':
        return _post_upload(params, files, session, submission)
    raise MethodNotAllowed('Nope')


def delete_all(method: str, params: MultiDict, session: Session,
               submission_id: int, token: str) -> Response:
    """
    Handle a request to delete all files in the workspace.

    Parameters
    ----------
    method : str
        ``GET`` or ``POST``
    params : :class:`MultiDict`
        The query or form data from the request.
    session : :class:`Session`
        The authenticated session for the request.
    submission_id : int
        The identifier of the submission for which the deletion is being made.
    token : str
        The original (encrypted) auth token on the request. Used to perform
        subrequests to the file management service.

    Returns
    -------
    dict
        Response data, to render in template.
    int
        HTTP status code. This should be ``200`` or ``303``, unless something
        goes wrong.
    dict
        Extra headers to add/update on the response. This should include
        the `Location` header for use in the 303 redirect response, if
        applicable.

    """
    logger.debug('%s delete all files with params %s', method, params)
    submission, submission_events = load_submission(submission_id)
    upload_id = submission.source_content.identifier
    response_data = {
        'submission': submission,
        'submission_id': submission.submission_id,
    }
    filemanager.set_auth_token(token)
    if method == 'GET':
        form = DeleteAllFilesForm()
        response_data.update({'form': form})
        return response_data, status.HTTP_200_OK, {}
    elif method == 'POST':
        form = DeleteAllFilesForm(params)
        if form.validate() and form.confirmed.data:
            try:
                filemanager.delete_all(upload_id)
            except filemanager.RequestForbidden as e:
                alerts.flash_failure(Markup(
                    'There was a problem authorizing your request. Please try'
                    f' again. {PLEASE_CONTACT_SUPPORT}'
                ))
                logger.error('Encountered RequestForbidden: %s', e)
            except filemanager.BadRequest as e:
                alerts.flash_warning(Markup(
                    'Something odd happened when processing your request.'
                    f'{PLEASE_CONTACT_SUPPORT}'
                ))
                logger.error('Encountered BadRequest: %s', e)
            except filemanager.RequestFailed as e:
                alerts.flash_failure(Markup(
                    'There was a problem carrying out your request. Please try'
                    f' again. {PLEASE_CONTACT_SUPPORT}'
                ))
                logger.error('Encountered RequestFailed: %s', e)
            redirect = url_for('ui.file_upload', submission_id=submission_id)
            return {}, status.HTTP_303_SEE_OTHER, {'Location': redirect}
        response_data.update({'form': form})
        return response_data, status.HTTP_400_BAD_REQUEST, {}


def delete(method: str, params: MultiDict, session: Session,
           submission_id: int, token: str) -> Response:
    """
    Handle a request to delete a file.

    The file will only be deleted if a POST request is made that also contains
    the ``confirmed`` parameter.

    The process can be initiated with a GET request that contains the
    ``path`` (key) for the file to be deleted. For example, a button on
    the upload interface may link to the deletion route with the file path
    as a query parameter. This will generate a deletion confirmation form,
    which can be POSTed to complete the action.

    Parameters
    ----------
    method : str
        ``GET`` or ``POST``
    params : :class:`MultiDict`
        The query or form data from the request.
    session : :class:`Session`
        The authenticated session for the request.
    submission_id : int
        The identifier of the submission for which the deletion is being made.
    token : str
        The original (encrypted) auth token on the request. Used to perform
        subrequests to the file management service.

    Returns
    -------
    dict
        Response data, to render in template.
    int
        HTTP status code. This should be ``200`` or ``303``, unless something
        goes wrong.
    dict
        Extra headers to add/update on the response. This should include
        the `Location` header for use in the 303 redirect response, if
        applicable.

    """
    logger.debug('%s delete with params %s', method, params)
    submission, submission_events = load_submission(submission_id)
    upload_id = submission.source_content.identifier
    response_data = {
        'submission': submission,
        'submission_id': submission.submission_id,
    }
    filemanager.set_auth_token(token)

    if method == 'GET':
        # The only thing that we want to get from the request params on a GET
        # request is the file path. This way there is no way for a GET request
        # to trigger actual deletion. The user must explicitly indicate via
        # a valid POST that the file should in fact be deleted.
        form = DeleteFileForm(MultiDict({'file_path': params['path']}))
        response_data.update({'form': form})
        return response_data, status.HTTP_200_OK, {}
    elif method == 'POST':
        form = DeleteFileForm(params)
        if form.validate() and form.confirmed.data:
            try:
                filemanager.delete_file(upload_id, form.file_path.data)
                alerts.flash_success(
                    f'File <code>{form.file_path.data}</code> was deleted'
                    ' successfully', title='Deleted file successfully',
                    safe=True
                )
            except filemanager.RequestForbidden as e:
                alerts.flash_failure(Markup(
                    'There was a problem authorizing your request. Please try'
                    f' again. {PLEASE_CONTACT_SUPPORT}'
                ))
                logger.error('Encountered RequestForbidden: %s', e)
            except filemanager.BadRequest as e:
                alerts.flash_warning(Markup(
                    'Something odd happened when processing your request.'
                    f'{PLEASE_CONTACT_SUPPORT}'
                ))
                logger.error('Encountered BadRequest: %s', e)
            except filemanager.RequestFailed as e:
                alerts.flash_failure(Markup(
                    'There was a problem carrying out your request. Please try'
                    f' again. {PLEASE_CONTACT_SUPPORT}'
                ))
                logger.error('Encountered RequestFailed: %s', e)
            redirect = url_for('ui.file_upload', submission_id=submission_id)
            return {}, status.HTTP_303_SEE_OTHER, {'Location': redirect}
        response_data.update({'form': form})
        return response_data, status.HTTP_400_BAD_REQUEST, {}


class UploadForm(csrf.CSRFForm):
    """Form for uploading files."""

    file = FileField('Choose a file...',
                     validators=[validators.DataRequired()])
    ancillary = BooleanField('Ancillary')


class DeleteFileForm(csrf.CSRFForm):
    """Form for deleting individual files."""

    file_path = HiddenField('File', validators=[validators.DataRequired()])
    confirmed = BooleanField('Confirmed',
                             validators=[validators.DataRequired()])


class DeleteAllFilesForm(csrf.CSRFForm):
    """Form for deleting all files in the workspace."""

    confirmed = BooleanField('Confirmed',
                             validators=[validators.DataRequired()])


def _update_submission(submission: Submission, upload_status: Upload,
                       submitter: User, client: Optional[Client] = None) \
        -> Submission:
    """
    Update the :class:`.Submission` after an upload-related action.

    The submission is linked to the upload workspace via the
    :attr:`Submission.source_content` attribute. This is set using a
    :class:`SetUploadPackage` command. If the workspace identifier changes
    (e.g. on first upload), we want to execute :class:`SetUploadPackage` to
    make the association.

    Parameters
    ----------
    submission : :class:`Submission`
    upload_status : :class:`Upload`
    submitter : :class:`User`
    client : :class:`Client` or None

    """
    existing_upload = getattr(submission.source_content, 'identifier', None)
    if existing_upload == upload_status.identifier:
        return submission

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
        logger.error('Encountered SaveError while updating files for %i:'
                     ' %s', submission.submission_id, e)
        alerts.flash_failure(Markup(
            'There was a problem carrying out your request. Please try'
            f' again. {PLEASE_CONTACT_SUPPORT}'
        ))
        redirect = url_for('ui.file_upload',
                           submission_id=submission.submission_id)
        return {}, status.HTTP_303_SEE_OTHER, {'Location': redirect}
    return submission


def _get_upload(params: MultiDict, session: Session, submission: Submission) \
        -> Response:
    """
    Get the current state of the upload workspace, and prepare a response.

    Parameters
    ----------
    params : :class:`MultiDict`
        The query parameters from the request.
    session : :class:`Session`
        The authenticated session for the request.
    submission : :class:`Submission`
        The submission for which to retrieve upload workspace information.

    Returns
    -------
    dict
        Response data, to render in template.
    int
        HTTP status code.
    dict
        Extra headers to add/update on the response.

    """
    response_data = {
        'submission': submission,
        'submission_id': submission.submission_id,
        'status': None,
        'form': UploadForm()
    }
    if submission.source_content is None:
        # Nothing to show; should generate a blank-slate upload screen.
        return response_data, status.HTTP_200_OK, {}
    upload_id = submission.source_content.identifier
    status_data = alerts.get_hidden_alerts('status')
    logger.debug('Got status data from hidden alert: %s', status_data)
    if type(status_data) is dict and status_data['identifier'] == upload_id:
        print('! got status data from alert')
        upload_status = Upload.from_dict(status_data)
    else:
        try:
            upload_status = filemanager.get_upload_status(upload_id)
            print('! got status data from fm service', upload_status)
        except filemanager.RequestFailed as e:
            # TODO: handle specific failure cases.
            logger.error('Encountered RequestFailed getting data for'
                         ' for %i: %s', submission.submission_id, e)
            raise InternalServerError('Whoops') from e
    response_data.update({'status': upload_status})
    return response_data, status.HTTP_200_OK, {}


def _post_new_upload(params: MultiDict, pointer: FileStorage, session: Session,
                     submission: Submission) -> Response:
    """
    Handle a POST request with a new upload package.

    This occurs in the case that there is not already an upload workspace
    associated with the submission. See the :attr:`Submission.source_content`
    attribute, which is set using :class:`SetUploadPackage`.

    Parameters
    ----------
    params : :class:`MultiDict`
        The form data from the request.
    pointer : :class:`FileStorage`
        The file upload stream.
    session : :class:`Session`
        The authenticated session for the request.
    submission : :class:`Submission`
        The submission for which the upload is being made.

    Returns
    -------
    dict
        Response data, to render in template.
    int
        HTTP status code. This should be ``303``, unless something goes wrong.
    dict
        Extra headers to add/update on the response. This should include
        the `Location` header for use in the 303 redirect response.

    """
    submitter, client = util.user_and_client_from_session(session)

    # Using a form object provides some extra assurance that this is a legit
    # request; provides CSRF goodies.
    params['file'] = pointer
    form = UploadForm(params)
    if not form.validate():
        raise BadRequest('Invalid upload request')

    try:
        upload_status = filemanager.upload_package(pointer)
        submission = _update_submission(submission, upload_status, submitter,
                                        client)
        converted_size = tidy_filesize(upload_status.size)
        if upload_status.status is Upload.Status.READY:
            alerts.flash_success(
                f'Unpacked {upload_status.file_count} files. Total submission'
                f' package size is {converted_size}',
                title='Upload successful'
            )
        elif upload_status.status is Upload.Status.READY_WITH_WARNINGS:
            alerts.flash_warning(
                f'Unpacked {upload_status.file_count} files. Total submission'
                f' package size is {converted_size}. See below for warnings.',
                title='Upload complete, with warnings'
            )
        elif upload_status.status is Upload.Status.ERRORS:
            alerts.flash_warning(
                f'Unpacked {upload_status.file_count} files. Total submission'
                f' package size is {converted_size}. See below for errors.',
                title='Upload complete, with errors'
            )
        alerts.flash_hidden(upload_status.to_dict(), 'status')
    except filemanager.RequestFailed as e:
        alerts.flash_failure(Markup(
            'There was a problem carrying out your request. Please try'
            f' again. {PLEASE_CONTACT_SUPPORT}'
        ))
    redirect = url_for('ui.file_upload',
                       submission_id=submission.submission_id)
    return {}, status.HTTP_303_SEE_OTHER, {'Location': redirect}


def _post_new_file(params: MultiDict, pointer: FileStorage, session: Session,
                   submission: Submission) -> Response:
    """
    Handle a POST request with a new file to add to an existing upload package.

    This occurs in the case that there is already an upload workspace
    associated with the submission. See the :attr:`Submission.source_content`
    attribute, which is set using :class:`SetUploadPackage`.

    Parameters
    ----------
    params : :class:`MultiDict`
        The form data from the request.
    pointer : :class:`FileStorage`
        The file upload stream.
    session : :class:`Session`
        The authenticated session for the request.
    submission : :class:`Submission`
        The submission for which the upload is being made.

    Returns
    -------
    dict
        Response data, to render in template.
    int
        HTTP status code. This should be ``303``, unless something goes wrong.
    dict
        Extra headers to add/update on the response. This should include
        the `Location` header for use in the 303 redirect response.

    """
    submitter, client = util.user_and_client_from_session(session)
    upload_id = submission.source_content.identifier

    # Using a form object provides some extra assurance that this is a legit
    # request; provides CSRF goodies.
    params['file'] = pointer
    form = UploadForm(params)
    if not form.validate():
        logger.error('Invalid upload form: %s', form.errors)

        alerts.flash_failure("Something went wrong. Please try again.",
                             title="Whoops")
        redirect = url_for('ui.file_upload',
                           submission_id=submission.submission_id)
        return {}, status.HTTP_303_SEE_OTHER, {'Location': redirect}
    ancillary: bool = form.ancillary.data

    try:
        upload_status = filemanager.add_file(upload_id, pointer,
                                             ancillary=ancillary)
        submission = _update_submission(submission, upload_status, submitter,
                                        client)
        converted_size = tidy_filesize(upload_status.size)
        print(upload_status.status)
        if upload_status.status is Upload.Status.READY:
            alerts.flash_success(
                f'Uploaded {pointer.filename} successfully. Total submission'
                f' package size is {converted_size}',
                title='Upload successful'
            )
        elif upload_status.status is Upload.Status.READY_WITH_WARNINGS:
            alerts.flash_warning(
                f'Uploaded {pointer.filename} successfully. Total submission'
                f' package size is {converted_size}. See below for warnings.',
                title='Upload complete, with warnings'
            )
        elif upload_status.status is Upload.Status.ERRORS:
            alerts.flash_warning(
                f'Uploaded {pointer.filename} successfully. Total submission'
                f' package size is {converted_size}. See below for errors.',
                title='Upload complete, with errors'
            )
        status_data = upload_status.to_dict()
        logger.debug('Stashing status data for next page: %s', status_data)
        alerts.flash_hidden(status_data, 'status')
    except filemanager.RequestFailed as e:
        alerts.flash_failure(Markup(
            'There was a problem carrying out your request. Please try'
            f' again. {PLEASE_CONTACT_SUPPORT}'
        ))

    redirect = url_for('ui.file_upload',
                       submission_id=submission.submission_id)
    return {}, status.HTTP_303_SEE_OTHER, {'Location': redirect}


def _post_upload(params: MultiDict, files: MultiDict, session: Session,
                 submission: Submission) -> Response:
    """
    Compose POST request handling for the file upload endpoint.

    See the :attr:`Submission.source_content` attribute, which is set using
    :class:`SetUploadPackage`.

    Parameters
    ----------
    params : :class:`MultiDict`
        The form data from the request.
    files : :class:`MultiDict`
        File data in the multipart request. Values should be
        :class:`FileStorage` instances.
    session : :class:`Session`
        The authenticated session for the request.
    submission : :class:`Submission`
        The submission for which the request is being made.

    Returns
    -------
    dict
        Response data, to render in template.
    int
        HTTP status code. This should be ``303``, unless something goes wrong.
    dict
        Extra headers to add/update on the response. This should include
        the `Location` header for use in the 303 redirect response.

    """
    logger.debug('POST upload with params %s and files %s', params, files)
    logger.debug('POST upload with submission %s', submission)
    try:    # Make sure that we have a file to work with.
        pointer = files['file']
    except KeyError as e:   # User is going back, saving/exiting, or next step.
        headers = {}

        # Don't flash a message if the user is just trying to go back to the
        # previous page.
        if params.get('action') != 'previous':
            alerts.flash_failure(Markup('Please select a file to upload'))
            redirect = url_for('ui.file_upload',
                               submission_id=submission.submission_id)
            headers['Location'] = redirect
        return {}, status.HTTP_303_SEE_OTHER, headers

    if submission.source_content is None:   # New upload package.
        logger.debug('No existing source_content')
        return _post_new_upload(params, pointer, session, submission)
    logger.debug('Submission has source content')
    return _post_new_file(params, pointer, session, submission)
