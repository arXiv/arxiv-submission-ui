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

from arxiv.integration.api import status, service
from arxiv.submission.domain.submission import SubmissionContent
from arxiv.base import logging
from arxiv.base.globals import get_application_config, get_application_global
from werkzeug.datastructures import FileStorage

from submit.domain import Upload, FileStatus, FileError

logger = logging.getLogger(__name__)


class Download(object):
    """Wrapper around response content."""

    def __init__(self, response: requests.Response) -> None:
        """Initialize with a :class:`requests.Response` object."""
        self._response = response

    def read(self) -> bytes:
        """Read response content."""
        return self._response.content


class FileManager(service.HTTPIntegration):
    """Encapsulates a connection with the file management service."""

    VERSION = '0.0'
    SERVICE = 'filemanager'

    class Meta:
        """Configuration for :class:`FileManager`."""

        service_name = "file_manager"

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
            compressed_size=data['upload_compressed_size'],
            size=data['upload_total_size'],
            checksum=data['checksum'],
            source_format=SubmissionContent.Format(data['source_format'])
        )

    def request_file(self, path: str, token: str) -> Tuple[Download, dict]:
        """Perform a GET request for a file, and handle any exceptions."""
        response = self.request('get', path, token, stream=True)
        return Download(response), response.headers

    def upload_package(self, pointer: FileStorage, token: str) -> Upload:
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
        token : str
            Auth token to include in the request.

        Returns
        -------
        dict
            A description of the upload package.
        dict
            Response headers.

        """
        files = {'file': (pointer.filename, pointer, pointer.mimetype)}
        data, _, _ = self.json('post', '/', token, files=files,
                               expected_code=[status.CREATED,
                                              status.OK])
        return self._parse_upload_status(data)

    def get_upload_status(self, upload_id: int, token: str) -> Upload:
        """
        Retrieve metadata about an accepted and processed upload package.

        Parameters
        ----------
        upload_id : int
            Unique long-lived identifier for the upload.
        token : str
            Auth token to include in the request.

        Returns
        -------
        dict
            A description of the upload package.
        dict
            Response headers.

        """
        data, _, _ = self.json('get', f'/{upload_id}', token)
        return self._parse_upload_status(data)

    def add_file(self, upload_id: int, pointer: FileStorage, token: str,
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
        token : str
            Auth token to include in the request.
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
        data, _, _ = self.json('post', f'/{upload_id}', token,
                               data={'ancillary': ancillary}, files=files,
                               expected_code=[status.CREATED,
                                              status.OK])
        return self._parse_upload_status(data)

    def delete_all(self, upload_id: str, token: str) -> None:
        """
        Delete all files in the workspace.

        Does not delete the workspace itself.

        Parameters
        ----------
        upload_id : str
            Unique long-lived identifier for the upload.
        token : str
            Auth token to include in the request.

        """
        data, _, _ = self.json('post', f'/{upload_id}/delete_all', token)
        return self._parse_upload_status(data)

    def get_file_content(self, upload_id: str, file_path: str, token: str) \
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
        token : str
            Auth token to include in the request.

        Returns
        -------
        :class:`Download`
            A ``read() -> bytes``-able wrapper around response content.
        dict
            Response headers.

        """
        return self.request_file(f'/{upload_id}/{file_path}/content', token)

    def delete_file(self, upload_id: str, file_path: str, token: str) \
            -> Tuple[dict, dict]:
        """
        Delete a single file from the upload workspace.

        Parameters
        ----------
        upload_id : str
            Unique long-lived identifier for the upload.
        file_path : str
            Path-like key for individual file in upload workspace. This is the
            path relative to the root of the workspace.
        token : str
            Auth token to include in the request.

        Returns
        -------
        dict
            An empty dict.
        dict
            Response headers.

        """
        data, _, _ = self.json('delete', f'/{upload_id}/{file_path}', token)
        return self._parse_upload_status(data)

    def get_upload_content(self, upload_id: str, token: str) \
            -> Tuple[Download, dict]:
        """
        Retrieve the sanitized/processed upload package.

        Parameters
        ----------
        upload_id : str
            Unique long-lived identifier for the upload.
        token : str
            Auth token to include in the request.

        Returns
        -------
        :class:`Download`
            A ``read() -> bytes``-able wrapper around response content.
        dict
            Response headers.

        """
        return self.request_file(f'/{upload_id}/content', token)

    def get_logs(self, upload_id: str, token: str) -> Tuple[dict, dict]:
        """
        Retrieve log files related to upload workspace.

        Indicates history or actions on workspace.

        Parameters
        ----------
        upload_id : str
            Unique long-lived identifier for the upload.
        token : str
            Auth token to include in the request.

        Returns
        -------
        dict
            Log data for the upload workspace.
        dict
            Response headers.

        """
        data, _, headers = self.json('post', f'/{upload_id}/logs', token)
        return data, headers
