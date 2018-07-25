from unittest import TestCase, mock
import io
import tempfile
from urllib.parse import urlparse
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge, \
    Unauthorized, Forbidden
from werkzeug.datastructures import FileStorage
from flask import Blueprint, jsonify, Flask, request
from arxiv import status
from .. import filemanager

blueprint = Blueprint('filemanager', __name__)


class ResponseWrapper(object):
    """Provide a :class:`requests.Response`-like API for Flask responses."""

    def __init__(self, resp):
        self.resp = resp

    def json(self):
        return self.resp.json

    @property
    def status_code(self):
        return self.resp.status_code

    @property
    def headers(self):
        return self.resp.headers

    @property
    def content(self):
        return self.resp.data


@blueprint.route('/status')
def service_status():
    """Mock implementation of service status route."""
    return jsonify({'status': 'ok'})


@blueprint.route('/', methods=['POST'])
def upload_package():
    """Mock implementation of upload route."""
    if 'file' not in request.files:
        raise BadRequest('No file')
    if len(request.files['file'].read()) > 80:  # Arbitrary limit.
        raise RequestEntityTooLarge('Nope!')
    if 'Authorization' not in request.headers:
        raise Unauthorized('Nope!')
    if request.headers['Authorization'] != '!':     # Arbitrary value.
        raise Forbidden('No sir!')
    # Not sure what the response will look like yet.
    return jsonify({'upload': True}), status.HTTP_201_CREATED


class TestGetStatus(TestCase):
    """Get the file management service status."""

    def setUp(self):
        """Initialize a mock file management service."""
        self.service = Flask('filemanager')
        self.service.register_blueprint(blueprint)
        self.client = self.service.test_client()

    def get(self, path, *args, **kwargs):
        """Mock get request with Flask test client."""
        target = urlparse(path).path
        return ResponseWrapper(self.client.get(target, *args, **kwargs))

    @mock.patch(f'{filemanager.__name__}.requests.Session')
    def test_get_status(self, mock_Session):
        """Get the status endpoint for the file management service."""
        mock_session = mock.MagicMock(get=self.get)
        mock_Session.return_value = mock_session
        fm = filemanager.FileManagementService('https://foo.somewhere.org')
        data, headers = fm.get_service_status()
        self.assertEqual(data['status'], 'ok')


class TestUploadPackage(TestCase):
    """Create a new file upload package/workspace."""

    def setUp(self):
        """Initialize a mock file management service."""
        self.service = Flask('filemanager')
        self.service.register_blueprint(blueprint)
        self.client = self.service.test_client()
        self.headers = {}

    def get(self, path, *args, **kwargs):
        """Mock get request with Flask test client."""
        target = urlparse(path).path
        kwargs.update({'headers': self.headers})
        return ResponseWrapper(self.client.get(target, *args, **kwargs))

    def post(self, path, *args, **kwargs):
        """Mock post request with Flask test client."""
        target = urlparse(path).path
        filename, pointer, mimetype = kwargs.pop('files')['file']
        kwargs.update({'data': {'file': (pointer, filename)}})
        kwargs.update({'headers': self.headers})
        return ResponseWrapper(self.client.post(target, *args, **kwargs))

    @mock.patch(f'{filemanager.__name__}.requests.Session')
    def test_upload_package(self, mock_Session):
        """Create a new file upload package/workspace."""
        mock_session = mock.MagicMock(get=self.get, post=self.post,
                                      headers=self.headers)
        mock_Session.return_value = mock_session
        fm = filemanager.FileManagementService('https://foo.somewhere.org',
                                               headers={'Authorization': '!'})
        _, fname = tempfile.mkstemp()
        with open(fname, 'w') as f:
            f.write('foo content')

        pointer = FileStorage(open(fname, 'rb'), filename=fname,
                              content_type='application/tar+gz')
        data, headers = fm.upload_package(pointer)
        self.assertEqual(data['upload'], True)

    @mock.patch(f'{filemanager.__name__}.requests.Session')
    def test_upload_unauthorized(self, mock_Session):
        """An auth header is not included in the request."""
        mock_session = mock.MagicMock(get=self.get, post=self.post,
                                      headers=self.headers)
        mock_Session.return_value = mock_session
        fm = filemanager.FileManagementService('https://foo.somewhere.org',
                                               headers={})
        _, fname = tempfile.mkstemp()
        with open(fname, 'w') as f:
            f.write('foo content')

        pointer = FileStorage(open(fname, 'rb'), filename=fname,
                              content_type='application/tar+gz')
        with self.assertRaises(filemanager.RequestUnauthorized):
            fm.upload_package(pointer)

    @mock.patch(f'{filemanager.__name__}.requests.Session')
    def test_upload_forbidden(self, mock_Session):
        """The auth token does not grant sufficient privileges."""
        mock_session = mock.MagicMock(get=self.get, post=self.post,
                                      headers=self.headers)
        mock_Session.return_value = mock_session
        fm = filemanager.FileManagementService('https://foo.somewhere.org',
                                               headers={'Authorization': '?'})
        _, fname = tempfile.mkstemp()
        with open(fname, 'w') as f:
            f.write('foo content')

        pointer = FileStorage(open(fname, 'rb'), filename=fname,
                              content_type='application/tar+gz')
        with self.assertRaises(filemanager.RequestForbidden):
            fm.upload_package(pointer)

    @mock.patch(f'{filemanager.__name__}.requests.Session')
    def test_upload_oversize_package(self, mock_Session):
        """The file is too large."""
        mock_session = mock.MagicMock(get=self.get, post=self.post,
                                      headers=self.headers)
        mock_Session.return_value = mock_session
        fm = filemanager.FileManagementService('https://foo.somewhere.org',
                                               headers={'Authorization': '!'})
        _, fname = tempfile.mkstemp()
        with open(fname, 'w') as f:
            f.write('foo content' * 50)   # Bigger than arbitrary limit, above.

        pointer = FileStorage(open(fname, 'rb'), filename=fname,
                              content_type='application/tar+gz')
        with self.assertRaises(filemanager.Oversize):
            data, headers = fm.upload_package(pointer)
