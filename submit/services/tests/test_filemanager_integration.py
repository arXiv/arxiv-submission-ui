import os
from unittest import TestCase
import subprocess

from werkzeug.datastructures import FileStorage

from arxiv.base.globals import get_application_config
from arxiv.users.helpers import generate_token
from arxiv.users.auth import scopes
from .. import filemanager
from ...domain import UploadStatus, FileStatus, FileError


class TestFileManagerIntegration(TestCase):

    __test__ = int(bool(os.environ.get('WITH_INTEGRATION', False)))

    @classmethod
    def setUpClass(cls):
        """Start up the file manager service."""

        os.environ['JWT_SECRET'] = 'foosecret'
        os.environ['FILE_MANAGER_HOST'] = 'localhost'
        os.environ['FILE_MANAGER_PORT'] = '8002'
        os.environ['FILE_MANAGER_PROTO'] = 'http'
        os.environ['FILE_MANAGER_PATH'] = '/filemanager/api'
        os.environ['FILE_MANAGER_ENDPOINT'] = 'http://localhost:8002/filemanager/api'
        os.environ['FILE_MANAGER_VERIFY'] = '0'

        # print('starting file management service')
        # start_fm = subprocess.run(
        #     "docker run -d -p 8002:8000 arxiv/filemanager:0.1rc0",
        #     stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        #
        # if start_fm.returncode != 0:
        #     print(start_fm.stdout, start_fm.stderr)
        #     raise RuntimeError(
        #         f'Could not start file management service: {start_fm.stdout}.'
        #         f' Is one already running? Is port 8002 available?'
        #     )
        #
        # cls.fm_container = start_fm.stdout.decode('ascii').strip()
        # print(f'file management service started as {cls.fm_container}')

        cls.fm = filemanager.current_session()
        cls.token = generate_token('1', 'u@ser.com', 'theuser',
                                   scope=[scopes.WRITE_UPLOAD,
                                          scopes.READ_UPLOAD])

    @classmethod
    def tearDownClass(cls):
        """Tear down file management service once all tests have run."""
        # stop_fm = subprocess.run(f"docker rm -f {cls.fm_container}",
        #                          stdout=subprocess.PIPE,
        #                          stderr=subprocess.PIPE,
        #                          shell=True)

    def test_status(self):
        data, headers = self.fm.get_service_status()
        self.assertEqual(data['status'], 'OK')

    def test_upload_package(self):
        """Upload a new package."""
        fpath = os.path.join(os.path.split(os.path.abspath(__file__))[0],
                             'data', 'test.zip')
        pointer = FileStorage(open(fpath, 'rb'), filename='test.zip',
                              content_type='application/tar+gz')
        self.fm._session.headers.update({'Authorization': self.token})
        data = self.fm.upload_package(pointer)
        self.assertIsInstance(data, UploadStatus)
        self.assertEqual(data.status, UploadStatus.Statuses.READY)
        self.assertEqual(data.lifecycle, UploadStatus.LifecycleStates.ACTIVE)
        self.assertFalse(data.locked)

    def test_upload_package_without_authorization(self):
        """Upload a new package without authorization."""
        fpath = os.path.join(os.path.split(os.path.abspath(__file__))[0],
                             'data', 'test.zip')
        pointer = FileStorage(open(fpath, 'rb'), filename='test.zip',
                              content_type='application/tar+gz')
        token = generate_token('1', 'u@ser.com', 'theuser',
                               scope=[scopes.READ_UPLOAD])
        self.fm._session.headers.update({'Authorization': token})
        with self.assertRaises(filemanager.RequestForbidden):
            self.fm.upload_package(pointer)

    def test_upload_package_without_authentication_token(self):
        """Upload a new package without an authentication token."""
        fpath = os.path.join(os.path.split(os.path.abspath(__file__))[0],
                             'data', 'test.zip')
        pointer = FileStorage(open(fpath, 'rb'), filename='test.zip',
                              content_type='application/tar+gz')
        self.fm._session.headers.update({'Authorization': ''})
        with self.assertRaises(filemanager.RequestUnauthorized):
            self.fm.upload_package(pointer)

    def test_get_upload_status(self):
        """Get the status of an upload."""
        fpath = os.path.join(os.path.split(os.path.abspath(__file__))[0],
                             'data', 'test.zip')
        pointer = FileStorage(open(fpath, 'rb'), filename='test.zip',
                              content_type='application/tar+gz')
        self.fm._session.headers.update({'Authorization': self.token})
        data = self.fm.upload_package(pointer)

        status = self.fm.get_upload_status(data.identifier)
        self.assertIsInstance(status, UploadStatus)
        self.assertEqual(status.status, UploadStatus.Statuses.READY)
        self.assertEqual(status.lifecycle, UploadStatus.LifecycleState.ACTIVE)
        self.assertFalse(status.locked)

    def test_get_upload_status_without_authorization(self):
        """Get the status of an upload without the right scope."""
        fpath = os.path.join(os.path.split(os.path.abspath(__file__))[0],
                             'data', 'test.zip')
        pointer = FileStorage(open(fpath, 'rb'), filename='test.zip',
                              content_type='application/tar+gz')
        token = generate_token('1', 'u@ser.com', 'theuser',
                               scope=[scopes.WRITE_UPLOAD])
        self.fm._session.headers.update({'Authorization': token})
        data = self.fm.upload_package(pointer)

        with self.assertRaises(filemanager.RequestForbidden):
            self.fm.get_upload_status(data.identifier)

    def test_get_upload_status_nacho_upload(self):
        """Get the status of someone elses' upload."""
        fpath = os.path.join(os.path.split(os.path.abspath(__file__))[0],
                             'data', 'test.zip')
        pointer = FileStorage(open(fpath, 'rb'), filename='test.zip',
                              content_type='application/tar+gz')

        self.fm._session.headers.update({'Authorization': self.token})
        data = self.fm.upload_package(pointer)

        token = generate_token('2', 'other@ser.com', 'theotheruser',
                               scope=[scopes.READ_UPLOAD])
        self.fm._session.headers.update({'Authorization': token})
        with self.assertRaises(filemanager.RequestForbidden):
            self.fm.get_upload_status(data.identifier)

    def test_add_file_to_upload(self):
        """Add a file to an existing upload workspace."""
        fpath = os.path.join(os.path.split(os.path.abspath(__file__))[0],
                             'data', 'test.zip')
        pointer = FileStorage(open(fpath, 'rb'), filename='test.zip',
                              content_type='application/tar+gz')
        self.fm._session.headers.update({'Authorization': self.token})
        data = self.fm.upload_package(pointer)

        fpath2 = os.path.join(os.path.split(os.path.abspath(__file__))[0],
                              'data', 'test.txt')
        pointer2 = FileStorage(open(fpath2, 'rb'), filename='test.txt',
                               content_type='text/plain')
        status = self.fm.add_file(data.identifier, pointer2)
        self.assertIsInstance(status, UploadStatus)
        self.assertEqual(status.status, UploadStatus.Statuses.READY)
        self.assertEqual(status.lifecycle, UploadStatus.LifecycleState.ACTIVE)
        self.assertFalse(status.locked)
