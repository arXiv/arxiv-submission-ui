"""
Integration with the :mod:`filemanager` service API.

The file management service is responsible for accepting and processing user
uploads used for submissions. The core resource for the file management service
is the upload "workspace", which contains one or many files. We associate the
workspace with a submission prior to finalization. The workspace URI is used
for downstream processing, e.g. compilation.

A key requirement for this integration is the ability to stream uploads to
the file management service as they are being received by this UI application.
"""
from typing import Tuple
import json
from functools import wraps
from collections import defaultdict
from urllib.parse import urlparse, urlunparse, urlencode
import dateutil.parser
import requests
from requests.packages.urllib3.util.retry import Retry

from arxiv import status
from arxiv.base import logging
from arxiv.base.globals import get_application_config, get_application_global
from werkzeug.datastructures import FileStorage

from submit.domain import Upload, FileStatus, FileError

logger = logging.getLogger(__name__)


class RequestFailed(IOError):
    """The file management service returned an unexpected status code."""

    def __init__(self, msg: str, data: dict = {}) -> None:
        """Attach (optional) data to the exception."""
        self.data = data
        super(RequestFailed, self).__init__(msg)


class RequestUnauthorized(RequestFailed):
    """Client/user is not authenticated."""


class RequestForbidden(RequestFailed):
    """Client/user is not allowed to perform this request."""


class BadRequest(RequestFailed):
    """The request was malformed or otherwise improper."""


class Oversize(BadRequest):
    """The upload was too large."""


class BadResponse(RequestFailed):
    """The response from the file management service was malformed."""


class ConnectionFailed(IOError):
    """Could not connect to the file management service."""


class SecurityException(ConnectionFailed):
    """Raised when SSL connection fails."""


class Download(object):
    """Wrapper around response content."""

    def __init__(self, response: requests.Response) -> None:
        """Initialize with a :class:`requests.Response` object."""
        self._response = response

    def read(self) -> bytes:
        """Read response content."""
        return self._response.content


class FileManagementService(object):
    """Encapsulates a connection with the file management service."""

    def __init__(self, endpoint: str, verify_cert: bool = True,
                 headers: dict = {}) -> None:
        """
        Initialize an HTTP session.

        Parameters
        ----------
        endpoints : str
            URL for the root file management endpoint.
        verify_cert : bool
            Whether or not SSL certificate verification should enforced.
        headers : dict
            Headers to be included on all requests.

        """
        logger.debug('New FileManagementService with endpoint %s', endpoint)
        self._session = requests.Session()
        self._verify_cert = verify_cert
        self._retry = Retry(  # type: ignore
            total=10,
            read=10,
            connect=10,
            status=10,
            backoff_factor=0.5
        )
        self._adapter = requests.adapters.HTTPAdapter(max_retries=self._retry)
        self._session.mount(f'{urlparse(endpoint).scheme}://', self._adapter)
        if not endpoint.endswith('/'):
            endpoint += '/'
        self._endpoint = endpoint
        self._session.headers.update(headers)

    def _parse_upload_status(self, data: dict) -> Upload:
        file_errors = defaultdict(list)
        non_file_errors = []
        for etype, filename, message in data['errors']:
            if filename:
                file_errors[filename].append(FileError(etype.upper(), message))
            else:
                non_file_errors.append(FileError(etype.upper(), message))

        return Upload(
            started=dateutil.parser.parse(data['start_datetime']),
            completed=dateutil.parser.parse(data['completion_datetime']),
            created=dateutil.parser.parse(data['created_datetime']),
            modified=dateutil.parser.parse(data['modified_datetime']),
            status=Upload.Status(data['upload_status']),
            lifecycle=Upload.LifecycleStates(data['workspace_state']),
            locked=bool(data['lock_state'] == 'LOCKED'),
            identifier=data['upload_id'],
            files=[
                FileStatus(
                    name=fdata['name'],
                    path=fdata['public_filepath'],
                    size=fdata['size'],
                    file_type=fdata['type'],
                    modified=dateutil.parser.parse(fdata['modified_datetime']),
                    errors=file_errors[fdata['public_filepath']]
                ) for fdata in data['files']
            ],
            errors=non_file_errors,
            size=data['upload_total_size']
        )

    def _path(self, path: str, query: dict = {}) -> str:
        o = urlparse(self._endpoint)
        path = path.lstrip('/')
        return urlunparse((
            o.scheme, o.netloc, f"{o.path}{path}",
            None, urlencode(query), None
        ))

    def _make_request(self, method: str, path: str, expected_code: int = 200,
                      **kw) -> requests.Response:
        try:
            resp = getattr(self._session, method)(self._path(path), **kw)
        except requests.exceptions.SSLError as e:
            raise SecurityException('SSL failed: %s' % e) from e
        except requests.exceptions.ConnectionError as e:
            raise ConnectionFailed('Could not connect: %s' % e) from e
        if resp.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
            raise RequestFailed(f'Status: {resp.status_code}; {resp.content}')
        elif resp.status_code == status.HTTP_401_UNAUTHORIZED:
            raise RequestUnauthorized(f'Not authorized: {resp.content}')
        elif resp.status_code == status.HTTP_403_FORBIDDEN:
            raise RequestForbidden(f'Forbidden: {resp.content}')
        elif resp.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE:
            raise Oversize(f'Too large: {resp.content}')
        elif resp.status_code >= status.HTTP_400_BAD_REQUEST:
            raise BadRequest(f'Bad request: {resp.content}',
                             data=resp.content)
        elif resp.status_code is not expected_code:
            raise RequestFailed(f'Unexpected status code: {resp.status_code}')
        return resp

    def set_auth_token(self, token: str) -> None:
        """Set the authn/z token to use in subsequent requests."""
        self._session.headers.update({'Authorization': token})

    def request(self, method: str, path: str, expected_code: int = 200, **kw) \
            -> Tuple[dict, dict]:
        """Perform an HTTP request, and handle any exceptions."""
        resp = self._make_request(method, path, expected_code, **kw)

        # There should be nothing in a 204 response.
        if resp.status_code is status.HTTP_204_NO_CONTENT:
            return {}, resp.headers
        try:
            return resp.json(), resp.headers
        except json.decoder.JSONDecodeError as e:
            raise BadResponse('Could not decode: {resp.content}') from e

    def request_file(self, path: str, expected_code: int = 200, **kw) \
            -> Tuple[Download, dict]:
        """Perform a GET request for a file, and handle any exceptions."""
        kw.update({'stream': True})
        resp = self._make_request('get', expected_code, **kw)
        return Download(resp), resp.headers

    def get_service_status(self) -> dict:
        """Get the status of the file management service."""
        return self.request('get', 'status')

    def upload_package(self, pointer: FileStorage) -> Upload:
        """
        Stream an upload to the file management service.

        If the file is an archive (zip, tar-ball, etc), it will be unpacked.
        A variety of processing and sanitization routines are performed, and
        any errors or warnings (including deleted files) will be included in
        the response body.

        Parameters
        ----------
        pointer : :class:`FileStorage`
            File upload stream from the client.

        Returns
        -------
        dict
            A description of the upload package.
        dict
            Response headers.
        """
        files = {'file': (pointer.filename, pointer, pointer.mimetype)}
        data, headers = self.request('post', '/', files=files,
                                     expected_code=status.HTTP_201_CREATED)
        return self._parse_upload_status(data)

    def get_upload_status(self, upload_id: int) -> Upload:
        """
        Retrieve metadata about an accepted and processed upload package.

        Parameters
        ----------
        upload_id : int
            Unique long-lived identifier for the upload.

        Returns
        -------
        dict
            A description of the upload package.
        dict
            Response headers.

        """
        data, headers = self.request('get', f'/{upload_id}')
        upload_status = self._parse_upload_status(data)
        return upload_status

    def add_file(self, upload_id: int, pointer: FileStorage,
                 ancillary: bool = False) -> Upload:
        """
        Upload a file or package to an existing upload workspace.

        If the file is an archive (zip, tar-ball, etc), it will be unpacked. A
        variety of processing and sanitization routines are performed. Existing
        files will be overwritten by files of the  same name. and any errors or
        warnings (including deleted files) will be included in the response
        body.

        Parameters
        ----------
        upload_id : int
            Unique long-lived identifier for the upload.
        pointer : :class:`FileStorage`
            File upload stream from the client.
        ancillary : bool
            If ``True``, the file should be added as an ancillary file.

        Returns
        -------
        dict
            A description of the upload package.
        dict
            Response headers.

        """
        files = {'file': (pointer.filename, pointer, pointer.mimetype)}
        data, headers = self.request('post', f'/{upload_id}',
                                     data={'ancillary': ancillary},
                                     files=files,
                                     expected_code=status.HTTP_201_CREATED)
        upload_status = self._parse_upload_status(data)
        return upload_status

    def delete_all(self, upload_id: str) -> None:
        """
        Delete all files in the workspace.

        Does not delete the workspace itself.

        Parameters
        ----------
        upload_id : str
            Unique long-lived identifier for the upload.

        """
        self.request('post', f'/{upload_id}/delete_all',
                     expected_code=status.HTTP_204_NO_CONTENT)
        return

    def get_file_content(self, upload_id: str, file_path: str) \
            -> Tuple[Download, dict]:
        """
        Get the content of a single file from the upload workspace.

        Parameters
        ----------
        upload_id : str
            Unique long-lived identifier for the upload.
        file_path : str
            Path-like key for individual file in upload workspace. This is the
            path relative to the root of the workspace.

        Returns
        -------
        :class:`Download`
            A ``read() -> bytes``-able wrapper around response content.
        dict
            Response headers.
        """
        return self.request_file(f'/{upload_id}/{file_path}/content')

    def delete_file(self, upload_id: str, file_path: str) -> Tuple[dict, dict]:
        """
        Delete a single file from the upload workspace.

        Parameters
        ----------
        upload_id : str
            Unique long-lived identifier for the upload.
        file_path : str
            Path-like key for individual file in upload workspace. This is the
            path relative to the root of the workspace.

        Returns
        -------
        dict
            An empty dict.
        dict
            Response headers.
        """
        return self.request('delete', f'/{upload_id}/{file_path}',
                            expected_code=status.HTTP_204_NO_CONTENT)

    def get_upload_content(self, upload_id: str) -> Tuple[Download, dict]:
        """
        Retrieve the sanitized/processed upload package.

        Parameters
        ----------
        upload_id : str
            Unique long-lived identifier for the upload.

        Returns
        -------
        :class:`Download`
            A ``read() -> bytes``-able wrapper around response content.
        dict
            Response headers.

        """
        return self.request_file(f'/{upload_id}/content')

    def get_logs(self, upload_id: str) -> Tuple[dict, dict]:
        """
        Retrieve log files related to upload workspace.

        Indicates history or actions on workspace.

        Parameters
        ----------
        upload_id : str
            Unique long-lived identifier for the upload.

        Returns
        -------
        dict
            Log data for the upload workspace.
        dict
            Response headers.

        """
        return self.request('post', f'/{upload_id}/logs')


def init_app(app: object = None) -> None:
    """Set default configuration parameters for an application instance."""
    config = get_application_config(app)
    config.setdefault('FILE_MANAGER_ENDPOINT', 'https://arxiv.org/')
    config.setdefault('FILE_MANAGER_VERIFY', True)


def get_session(app: object = None) -> FileManagementService:
    """Get a new session with the file management endpoint."""
    config = get_application_config(app)
    endpoint = config.get('FILE_MANAGER_ENDPOINT', 'https://arxiv.org/')
    verify_cert = config.get('FILE_MANAGER_VERIFY', True)
    logger.debug('Create FileManagementService with endpoint %s', endpoint)
    return FileManagementService(endpoint, verify_cert=verify_cert)


def current_session() -> FileManagementService:
    """Get/create :class:`.FileManagementService` for this context."""
    g = get_application_global()
    if not g:
        return get_session()
    elif 'filemanager' not in g:
        g.filemanager = get_session()   # type: ignore
    return g.filemanager    # type: ignore


@wraps(FileManagementService.set_auth_token)
def set_auth_token(token: str) -> None:
    """See :meth:`FileManagementService.set_auth_token`."""
    return current_session().set_auth_token(token)


@wraps(FileManagementService.get_upload_status)
def get_upload_status(upload_id: int) -> Upload:
    """See :meth:`FileManagementService.get_upload_status`."""
    return current_session().get_upload_status(upload_id)


@wraps(FileManagementService.upload_package)
def upload_package(pointer: FileStorage) -> Upload:
    """See :meth:`FileManagementService.upload_package`."""
    return current_session().upload_package(pointer)


@wraps(FileManagementService.add_file)
def add_file(upload_id: int, pointer: FileStorage, ancillary: bool = False) \
        -> Upload:
    """See :meth:`FileManagementService.add_file`."""
    return current_session().add_file(upload_id, pointer, ancillary=ancillary)


@wraps(FileManagementService.delete_file)
def delete_file(upload_id: int, file_path: str) -> Upload:
    """See :meth:`FileManagementService.delete_file`."""
    return current_session().delete_file(upload_id, file_path)


def delete_all(upload_id: str) -> None:
    """See :meth:`FileManagementService.delete_all`."""
    return current_session().delete_all(upload_id)
