import os
from unittest import TestCase, mock
import subprocess
import time

from flask import Flask, Config
from werkzeug.datastructures import FileStorage

from arxiv.base.globals import get_application_config
from arxiv.integration.api import exceptions
from arxiv.users.helpers import generate_token
from arxiv.users.auth import scopes
from ..filemanager import FileManager
from ...domain import Upload, FileStatus, FileError

mock_app = Flask('test')
mock_app.config.update({
    'FILEMANAGER_ENDPOINT': 'http://localhost:8003/filemanager/api',
    'FILEMANAGER_VERIFY': False
})
FileManager.init_app(mock_app)


class TestFileManagerIntegration(TestCase):

    __test__ = int(bool(os.environ.get('WITH_INTEGRATION', False)))

    @classmethod
    def setUpClass(cls):
        """Start up the file manager service."""
        print('starting file management service')
        os.environ['JWT_SECRET'] = 'foosecret'
        start_fm = subprocess.run(
            'docker run -d -e JWT_SECRET=foosecret -p 8003:8000 arxiv/filemanager:df4d57e1 /bin/bash -c \'python bootstrap.py; uwsgi --http-socket :8000 -M -t 3000 --manage-script-name --processes 8 --threads 1 --async 100 --ugreen --mount /=/opt/arxiv/wsgi.py --logformat "%(addr) %(addr) - %(user_id)|%(session_id) [%(rtime)] [%(uagent)] \\"%(method) %(uri) %(proto)\\" %(status) %(size) %(micros) %(ttfb)"\'',
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)

        if start_fm.returncode != 0:
            print(start_fm.stdout, start_fm.stderr)
            raise RuntimeError(
                f'Could not start file management service: {start_fm.stdout}.'
                f' Is one already running? Is port 8003 available?'
            )
        time.sleep(2)

        cls.fm_container = start_fm.stdout.decode('ascii').strip()
        print(f'file management service started as {cls.fm_container}')

        cls.token = generate_token('1', 'u@ser.com', 'theuser',
                                   scope=[scopes.WRITE_UPLOAD,
                                          scopes.READ_UPLOAD])

    @classmethod
    def tearDownClass(cls):
        """Tear down file management service once all tests have run."""
        stop_fm = subprocess.run(f"docker rm -f {cls.fm_container}",
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 shell=True)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    def test_upload_package(self):
        """Upload a new package."""
        fpath = os.path.join(os.path.split(os.path.abspath(__file__))[0],
                             'data', 'test.zip')
        pointer = FileStorage(open(fpath, 'rb'), filename='test.zip',
                              content_type='application/tar+gz')
        data = FileManager.upload_package(pointer, self.token)
        self.assertIsInstance(data, Upload)
        self.assertEqual(data.status, Upload.Status.ERRORS)
        self.assertEqual(data.lifecycle, Upload.LifecycleStates.ACTIVE)
        self.assertFalse(data.locked)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    def test_upload_package_without_authorization(self):
        """Upload a new package without authorization."""
        fpath = os.path.join(os.path.split(os.path.abspath(__file__))[0],
                             'data', 'test.zip')
        pointer = FileStorage(open(fpath, 'rb'), filename='test.zip',
                              content_type='application/tar+gz')
        token = generate_token('1', 'u@ser.com', 'theuser',
                               scope=[scopes.READ_UPLOAD])
        with self.assertRaises(exceptions.RequestForbidden):
            FileManager.upload_package(pointer, token)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    def test_upload_package_without_authentication_token(self):
        """Upload a new package without an authentication token."""
        fpath = os.path.join(os.path.split(os.path.abspath(__file__))[0],
                             'data', 'test.zip')
        pointer = FileStorage(open(fpath, 'rb'), filename='test.zip',
                              content_type='application/tar+gz')
        with self.assertRaises(exceptions.RequestUnauthorized):
            FileManager.upload_package(pointer, '')

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    def test_get_upload_status(self):
        """Get the status of an upload."""
        fpath = os.path.join(os.path.split(os.path.abspath(__file__))[0],
                             'data', 'test.zip')
        pointer = FileStorage(open(fpath, 'rb'), filename='test.zip',
                              content_type='application/tar+gz')
        data = FileManager.upload_package(pointer, self.token)

        status = FileManager.get_upload_status(data.identifier, self.token)
        self.assertIsInstance(status, Upload)
        self.assertEqual(status.status, Upload.Status.ERRORS)
        self.assertEqual(status.lifecycle, Upload.LifecycleStates.ACTIVE)
        self.assertFalse(status.locked)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    def test_get_upload_status_without_authorization(self):
        """Get the status of an upload without the right scope."""
        fpath = os.path.join(os.path.split(os.path.abspath(__file__))[0],
                             'data', 'test.zip')
        pointer = FileStorage(open(fpath, 'rb'), filename='test.zip',
                              content_type='application/tar+gz')
        token = generate_token('1', 'u@ser.com', 'theuser',
                               scope=[scopes.WRITE_UPLOAD])
        data = FileManager.upload_package(pointer, self.token)

        with self.assertRaises(exceptions.RequestForbidden):
            FileManager.get_upload_status(data.identifier, token)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    def test_get_upload_status_nacho_upload(self):
        """Get the status of someone elses' upload."""
        fpath = os.path.join(os.path.split(os.path.abspath(__file__))[0],
                             'data', 'test.zip')
        pointer = FileStorage(open(fpath, 'rb'), filename='test.zip',
                              content_type='application/tar+gz')

        data = FileManager.upload_package(pointer, self.token)

        token = generate_token('2', 'other@ser.com', 'theotheruser',
                               scope=[scopes.READ_UPLOAD])
        with self.assertRaises(exceptions.RequestForbidden):
            FileManager.get_upload_status(data.identifier, token)

    @mock.patch('arxiv.integration.api.service.current_app', mock_app)
    def test_add_file_to_upload(self):
        """Add a file to an existing upload workspace."""
        fpath = os.path.join(os.path.split(os.path.abspath(__file__))[0],
                             'data', 'test.zip')
        pointer = FileStorage(open(fpath, 'rb'), filename='test.zip',
                              content_type='application/tar+gz')
        data = FileManager.upload_package(pointer, self.token)

        fpath2 = os.path.join(os.path.split(os.path.abspath(__file__))[0],
                              'data', 'test.txt')
        pointer2 = FileStorage(open(fpath2, 'rb'), filename='test.txt',
                               content_type='text/plain')
        fm = FileManager.current_session()
        status = fm.add_file(data.identifier, pointer2, self.token)
        from pprint import pprint
        pprint(status)
        self.assertIsInstance(status, Upload)
        self.assertEqual(status.status, Upload.Status.ERRORS)
        self.assertEqual(status.lifecycle, Upload.LifecycleStates.ACTIVE)
        self.assertFalse(status.locked)
