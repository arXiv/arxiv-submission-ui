"""
Controllers for upload-related requests.

Things that still need to be done:

- Display error alerts from the file management service.
- Show warnings/errors for individual files in the table. We may need to
  extend the flashing mechanism to "flash" data to the next page (without
  displaying it as a notification to the user).

"""

from typing import Tuple, Dict, Any, Optional, List

from werkzeug import MultiDict
from werkzeug.exceptions import InternalServerError, BadRequest, \
    MethodNotAllowed
from werkzeug.datastructures import FileStorage

from wtforms import BooleanField, widgets, HiddenField, FileField
from wtforms.validators import DataRequired
from flask import url_for, Markup

from arxiv import status
from arxiv.base import logging, alerts
from arxiv.forms import csrf
from arxiv.submission.domain.submission import SubmissionContent
from arxiv.submission import SetUploadPackage, UpdateUploadPackage, save, \
    Submission, User, Client
from arxiv.submission.exceptions import InvalidStack, SaveError
from arxiv.users.domain import Session

from .util import validate_command, user_and_client_from_session
from ..util import load_submission, tidy_filesize
from ..services import filemanager
from ..domain import Upload

logger = logging.getLogger(__name__)

Response = Tuple[Dict[str, Any], int, Dict[str, Any]]  # pylint: disable=C0103

PLEASE_CONTACT_SUPPORT = Markup(
    'If you continue to experience problems, please contact'
    ' <a href="mailto:help@arxiv.org"> arXiv support</a>.'
)


def upload_files(method: str, params: MultiDict, session: Session,
                 submission_id: int, files: Optional[MultiDict] = None,
                 token: Optional[str] = None, **kwargs) -> Response:
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
    if files is None or token is None:
        raise BadRequest("Missing files or auth token")

    submission, _ = load_submission(submission_id)

    rdata = {'submission_id': submission_id, 'submission': submission}

    if method == 'GET':
        return _get_upload(params, session, submission, rdata)

    # User is attempting an upload of some kind.
    elif method == 'POST':
        if params.get('action') in ['previous', 'next', 'save_exit']:
            # User is not actually trying to upload anything; let flow control
            # in the routes handle the response.
            return {}, status.HTTP_303_SEE_OTHER, {}
        # Otherwise, treat this as an upload attempt.
        return _post_upload(params, files, session, submission, rdata)
    raise MethodNotAllowed('Nope')


def delete_all(method: str, params: MultiDict, session: Session,
               submission_id: int, token: Optional[str] = None,
               **kwargs) -> Response:
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
    if token is None:
        raise BadRequest('Missing auth token')

    submission, submission_events = load_submission(submission_id)
    upload_id = submission.source_content.identifier
    submitter, client = user_and_client_from_session(session)

    rdata = {'submission': submission, 'submission_id': submission_id}

    if method == 'GET':
        form = DeleteAllFilesForm()
        rdata.update({'form': form})
        return rdata, status.HTTP_200_OK, {}
    elif method == 'POST':
        form = DeleteAllFilesForm(params)
        rdata.update({'form': form})

        if not (form.validate() and form.confirmed.data):
            raise BadRequest(rdata)

        try:
            stat = filemanager.delete_all(upload_id)
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

        command = UpdateUploadPackage(creator=submitter, client=client,
                                      checksum=stat.checksum,
                                      uncompressed_size=stat.size,
                                      source_format=stat.source_format)

        if not validate_command(form, command, submission):
            raise BadRequest(rdata)

        try:
            submission, _ = save(command, submission_id=submission_id)
        except SaveError:
            alerts.flash_failure(Markup(
                'There was a problem carrying out your request. Please try'
                f' again. {PLEASE_CONTACT_SUPPORT}'
            ))

        redirect = url_for('ui.file_upload', submission_id=submission_id)
        return {}, status.HTTP_303_SEE_OTHER, {'Location': redirect}
    raise MethodNotAllowed('Method not supported')


def delete(method: str, params: MultiDict, session: Session,
           submission_id: int, token: Optional[str] = None,
           **kwargs) -> Response:
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
    if token is None:
        raise BadRequest('Missing auth token')

    submission, submission_events = load_submission(submission_id)
    upload_id = submission.source_content.identifier
    submitter, client = user_and_client_from_session(session)

    rdata = {'submission': submission, 'submission_id': submission_id}

    if method == 'GET':
        # The only thing that we want to get from the request params on a GET
        # request is the file path. This way there is no way for a GET request
        # to trigger actual deletion. The user must explicitly indicate via
        # a valid POST that the file should in fact be deleted.
        params = MultiDict({'file_path': params['path']})

    form = DeleteFileForm(params)
    rdata.update({'form': form})

    if method == 'POST':
        if not (form.validate() and form.confirmed.data):
            raise BadRequest(rdata)

        stat: Optional[Upload] = None
        try:
            stat = filemanager.delete_file(upload_id, form.file_path.data)
            alerts.flash_success(
                f'File <code>{form.file_path.data}</code> was deleted'
                ' successfully', title='Deleted file successfully',
                safe=True
            )
        except filemanager.RequestForbidden:
            alerts.flash_failure(Markup(
                'There was a problem authorizing your request. Please try'
                f' again. {PLEASE_CONTACT_SUPPORT}'
            ))
        except filemanager.BadRequest:
            alerts.flash_warning(Markup(
                'Something odd happened when processing your request.'
                f'{PLEASE_CONTACT_SUPPORT}'
            ))
        except filemanager.RequestFailed:
            alerts.flash_failure(Markup(
                'There was a problem carrying out your request. Please try'
                f' again. {PLEASE_CONTACT_SUPPORT}'
            ))

        if stat is not None:
            command = UpdateUploadPackage(creator=submitter,
                                          checksum=stat.checksum,
                                          uncompressed_size=stat.size,
                                          source_format=stat.source_format)
            if not validate_command(form, command, submission):
                raise BadRequest(rdata)

            try:
                submission, _ = save(command, submission_id=submission_id)
            except SaveError:
                alerts.flash_failure(Markup(
                    'There was a problem carrying out your request. Please try'
                    f' again. {PLEASE_CONTACT_SUPPORT}'
                ))
        redirect = url_for('ui.file_upload', submission_id=submission_id)
        return {}, status.HTTP_303_SEE_OTHER, {'Location': redirect}
    return rdata, status.HTTP_200_OK, {}


class UploadForm(csrf.CSRFForm):
    """Form for uploading files."""

    file = FileField('Choose a file...', validators=[DataRequired()])
    ancillary = BooleanField('Ancillary')


class DeleteFileForm(csrf.CSRFForm):
    """Form for deleting individual files."""

    file_path = HiddenField('File', validators=[DataRequired()])
    confirmed = BooleanField('Confirmed', validators=[DataRequired()])


class DeleteAllFilesForm(csrf.CSRFForm):
    """Form for deleting all files in the workspace."""

    confirmed = BooleanField('Confirmed', validators=[DataRequired()])


def _update(form: UploadForm, submission: Submission, stat: Upload,
            submitter: User, client: Optional[Client] = None,
            rdata: Dict[str, Any] = {}) -> Submission:
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
    _status : :class:`Upload`
    submitter : :class:`User`
    client : :class:`Client` or None

    """
    existing_upload = getattr(submission.source_content, 'identifier', None)

    if existing_upload == stat.identifier:
        command = UpdateUploadPackage(creator=submitter, client=client,
                                      checksum=stat.checksum,
                                      uncompressed_size=stat.size,
                                      source_format=stat.source_format)
    else:
        command = SetUploadPackage(creator=submitter, client=client,
                                   identifier=stat.identifier,
                                   checksum=stat.checksum,
                                   uncompressed_size=stat.size,
                                   source_format=stat.source_format)

    if not validate_command(form, command, submission):
        raise BadRequest(rdata)

    try:
        submission, _ = save(command, submission_id=submission.submission_id)
    except SaveError:
        alerts.flash_failure(Markup(
            'There was a problem carrying out your request. Please try'
            f' again. {PLEASE_CONTACT_SUPPORT}'
        ))
    rdata['submission'] = submission
    return submission


def _get_upload(params: MultiDict, session: Session, submission: Submission,
                rdata: Dict[str, Any]) -> Response:
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
    rdata.update({'status': None, 'form': UploadForm()})

    if submission.source_content is None:
        # Nothing to show; should generate a blank-slate upload screen.
        return rdata, status.HTTP_200_OK, {}

    upload_id = submission.source_content.identifier
    status_data = alerts.get_hidden_alerts('_status')

    if type(status_data) is dict and status_data['identifier'] == upload_id:
        stat = Upload.from_dict(status_data)
    else:
        try:
            stat = filemanager.get_upload_status(upload_id)
        except filemanager.RequestFailed as e:
            # TODO: handle specific failure cases.
            raise InternalServerError(rdata) from e
    rdata.update({'status': stat})
    if stat:
        rdata.update({'immediate_notifications': _get_notifications(stat)})
    return rdata, status.HTTP_200_OK, {}


def _new_upload(params: MultiDict, pointer: FileStorage, session: Session,
                submission: Submission, rdata: Dict[str, Any]) -> Response:
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
    submitter, client = user_and_client_from_session(session)

    # Using a form object provides some extra assurance that this is a legit
    # request; provides CSRF goodies.
    params['file'] = pointer
    form = UploadForm(params)
    rdata.update({'form': form})

    if not form.validate():
        raise BadRequest(rdata)

    try:
        stat = filemanager.upload_package(pointer)
    except filemanager.RequestFailed:
        alerts.flash_failure(Markup(
            'There was a problem carrying out your request. Please try'
            f' again. {PLEASE_CONTACT_SUPPORT}'
        ))

    submission = _update(form, submission, stat, submitter, client, rdata)
    converted_size = tidy_filesize(stat.size)
    if stat.status is Upload.Status.READY:
        alerts.flash_success(
            f'Unpacked {stat.file_count} files. Total submission'
            f' package size is {converted_size}',
            title='Upload successful'
        )
    elif stat.status is Upload.Status.READY_WITH_WARNINGS:
        alerts.flash_warning(
            f'Unpacked {stat.file_count} files. Total submission'
            f' package size is {converted_size}. See below for warnings.',
            title='Upload complete, with warnings'
        )
    elif stat.status is Upload.Status.ERRORS:
        alerts.flash_warning(
            f'Unpacked {stat.file_count} files. Total submission'
            f' package size is {converted_size}. See below for errors.',
            title='Upload complete, with errors'
        )
    alerts.flash_hidden(stat.to_dict(), '_status')

    loc = url_for('ui.file_upload', submission_id=submission.submission_id)
    return {}, status.HTTP_303_SEE_OTHER, {'Location': loc}


def _new_file(params: MultiDict, pointer: FileStorage, session: Session,
              submission: Submission, rdata: Dict[str, Any]) -> Response:
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
    submitter, client = user_and_client_from_session(session)
    upload_id = submission.source_content.identifier

    # Using a form object provides some extra assurance that this is a legit
    # request; provides CSRF goodies.
    params['file'] = pointer
    form = UploadForm(params)
    rdata['form'] = form

    if not form.validate():
        logger.error('Invalid upload form: %s', form.errors)

        alerts.flash_failure("Something went wrong. Please try again.",
                             title="Whoops")
        redirect = url_for('ui.file_upload',
                           submission_id=submission.submission_id)
        return {}, status.HTTP_303_SEE_OTHER, {'Location': redirect}
    ancillary: bool = form.ancillary.data

    try:
        stat = filemanager.add_file(upload_id, pointer, ancillary=ancillary)
    except filemanager.RequestFailed as e:
        alerts.flash_failure(Markup(
            'There was a problem carrying out your request. Please try'
            f' again. {PLEASE_CONTACT_SUPPORT}'
        ))
        raise InternalServerError(rdata) from e

    submission = _update(form, submission, stat, submitter, client, rdata)
    converted_size = tidy_filesize(stat.size)
    if stat.status is Upload.Status.READY:
        alerts.flash_success(
            f'Uploaded {pointer.filename} successfully. Total submission'
            f' package size is {converted_size}',
            title='Upload successful'
        )
    elif stat.status is Upload.Status.READY_WITH_WARNINGS:
        alerts.flash_warning(
            f'Uploaded {pointer.filename} successfully. Total submission'
            f' package size is {converted_size}. See below for warnings.',
            title='Upload complete, with warnings'
        )
    elif stat.status is Upload.Status.ERRORS:
        alerts.flash_warning(
            f'Uploaded {pointer.filename} successfully. Total submission'
            f' package size is {converted_size}. See below for errors.',
            title='Upload complete, with errors'
        )
    status_data = stat.to_dict()
    alerts.flash_hidden(status_data, '_status')
    loc = url_for('ui.file_upload', submission_id=submission.submission_id)
    return {}, status.HTTP_303_SEE_OTHER, {'Location': loc}


def _post_upload(params: MultiDict, files: MultiDict, session: Session,
                 submission: Submission, rdata: Dict[str, Any]) -> Response:
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
    try:    # Make sure that we have a file to work with.
        pointer = files['file']
    except KeyError:   # User is going back, saving/exiting, or next step.
        headers = {}

        # Don't flash a message if the user is just trying to go back to the
        # previous page.
        if params.get('action') != 'previous':
            alerts.flash_failure(Markup('Please select a file to upload'))
            submission_id = submission.submission_id
            headers['Location'] = url_for('ui.file_upload',
                                          submission_id=submission_id)
        return {}, status.HTTP_303_SEE_OTHER, headers

    if submission.source_content is None:   # New upload package.
        return _new_upload(params, pointer, session, submission, rdata)
    return _new_file(params, pointer, session, submission, rdata)


def _get_notifications(stat: Upload) -> List[Dict[str, str]]:
    # TODO: these need wordsmithing.
    notifications = []
    if not stat.files:   # Nothing in the upload workspace.
        return notifications
    if stat.status is Upload.Status.ERRORS:
        notifications.append({
            'title': 'Unresolved errors',
            'severity': 'danger',
            'body': 'There are unresolved problems with your submission'
                    ' files. Please correct the errors below before'
                    ' proceeding.'
        })
    elif stat.status is Upload.Status.READY_WITH_WARNINGS:
        notifications.append({
            'title': 'Warnings',
            'severity': 'warning',
            'body': 'There is one or more unresolved warning in the file list.'
                    ' You may proceed with your submission, but please note'
                    ' that these issues may cause delays in processing'
                    ' and/or announcement.'
        })
    if stat.source_format is SubmissionContent.Format.UNKNOWN:
        notifications.append({
            'title': 'Unknown submission type',
            'severity': 'warning',
            'body': 'We could not determine the source type of your'
                    ' submission. Please check your files carefully. We may'
                    ' not be able to process your files.'
        })
    elif stat.source_format is SubmissionContent.Format.INVALID:
        notifications.append({
            'title': 'Unsupported submission type',
            'severity': 'danger',
            'body': 'It is likely that your submission content is not'
                    ' supported. Please check your files carefully. We may not'
                    ' be able to process your files.'
        })
    else:
        notifications.append({
            'title': f'Detected {stat.source_format.value.upper()}',
            'severity': 'success',
            'body': 'Your submission content is supported.'
        })
    return notifications
