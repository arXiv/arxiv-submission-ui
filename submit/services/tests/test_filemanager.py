"""Tests for :mod:`submit.services.filemanager`."""

from unittest import TestCase, mock
import time
import json
from datetime import datetime
from threading import Thread, Event
import requests
import io
import tempfile
from urllib.parse import urlparse
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge, \
    Unauthorized, Forbidden
from werkzeug.datastructures import FileStorage
from flask import Blueprint, jsonify, Flask, request
from arxiv import status
from .. import filemanager
from ...tests import mock_filemanager


class TestGetStatus(TestCase):
    """Get the file management service status."""

    @classmethod
    def setUpClass(cls):
        """Start a single-threaded mock file management service."""
        app = mock_filemanager.create_fm_app()
        cls.host = '127.0.0.1'
        cls.port = '8900'

        def run_app():
            app.run(host=cls.host, port=cls.port)

        t = Thread(target=run_app)
        t.daemon = True
        t.start()
        time.sleep(2)    # Wait for app to be available.

    def test_get_status(self):
        """Get the status endpoint for the file management service."""
        service_endpoint = f'http://{self.host}:{self.port}'
        fm = filemanager.FileManagementService(service_endpoint)
        data, headers = fm.get_service_status()
        self.assertEqual(data['status'], 'ok')


class TestUploadPackage(TestCase):
    """Create a new file upload package/workspace."""

    @classmethod
    def setUpClass(cls):
        """Start a single-threaded mock file management service."""
        app = mock_filemanager.create_fm_app()
        cls.host = '127.0.0.1'
        cls.port = '8901'
        cls.service_endpoint = f'http://{cls.host}:{cls.port}'

        def run_app():
            app.run(host=cls.host, port=cls.port)

        t = Thread(target=run_app)
        t.daemon = True
        t.start()
        time.sleep(2)    # Wait for app to be available.

        cls.mock_data = json.dumps(dict(
            checksum='a1s2d3f4',
            size=593920,
            file_list=[
                dict(
                    path='',
                    name='thebestfile.pdf',
                    file_type='PDF',
                    added=datetime.now().isoformat(),
                    size=20505,
                    ancillary=False,
                    errors=[]
                )
            ],
            errors=[]
        ))

    def test_upload_package(self):
        """Create a new file upload package/workspace."""
        fm = filemanager.FileManagementService(self.service_endpoint,
                                               headers={'Authorization': '!'})
        _, fname = tempfile.mkstemp()
        with open(fname, 'w') as f:
            f.write(self.mock_data)

        pointer = FileStorage(open(fname, 'rb'), filename=fname,
                              content_type='application/tar+gz')
        data, headers = fm.upload_package(pointer)
        self.assertIn('identifier', data)

    def test_upload_unauthorized(self):
        """An auth header is not included in the request."""
        fm = filemanager.FileManagementService(self.service_endpoint,
                                               headers={})
        _, fname = tempfile.mkstemp()
        with open(fname, 'w') as f:
            f.write(self.mock_data)

        pointer = FileStorage(open(fname, 'rb'), filename=fname,
                              content_type='application/tar+gz')
        with self.assertRaises(filemanager.RequestUnauthorized):
            fm.upload_package(pointer)

    def test_upload_forbidden(self):
        """The auth token does not grant sufficient privileges."""
        fm = filemanager.FileManagementService(self.service_endpoint,
                                               headers={'Authorization': '?'})
        _, fname = tempfile.mkstemp()
        with open(fname, 'w') as f:
            f.write(self.mock_data)

        pointer = FileStorage(open(fname, 'rb'), filename=fname,
                              content_type='application/tar+gz')
        with self.assertRaises(filemanager.RequestForbidden):
            fm.upload_package(pointer)

    def test_upload_oversize_package(self):
        """The file is too large."""
        fm = filemanager.FileManagementService(self.service_endpoint,
                                               headers={'Authorization': '!'})
        _, fname = tempfile.mkstemp()
        with open(fname, 'w') as f:
            f.write(self.mock_data * 5000)   # Bigger than arbitrary limit.

        pointer = FileStorage(open(fname, 'rb'), filename=fname,
                              content_type='application/tar+gz')
        with self.assertRaises(filemanager.Oversize):
            data, headers = fm.upload_package(pointer)


class TestUploadFile(TestCase):
    """Upload a file to an existing upload workspace."""

    @classmethod
    def setUpClass(cls):
        """Start a single-threaded mock file management service."""
        app = mock_filemanager.create_fm_app()
        cls.host = '127.0.0.1'
        cls.port = '8902'
        cls.service_endpoint = f'http://{cls.host}:{cls.port}'

        def run_app():
            app.run(host=cls.host, port=cls.port)

        t = Thread(target=run_app)
        t.daemon = True
        t.start()
        time.sleep(2)    # Wait for app to be available.

        cls.mock_data = json.dumps(dict(
            path='',
            name='thebestfile.pdf',
            file_type='PDF',
            added=datetime.now().isoformat(),
            size=20505,
            ancillary=False,
            errors=[]
        ))

    def test_upload_file(self):
        """Upload a file to an upload package/workspace."""
        fm = filemanager.FileManagementService(self.service_endpoint,
                                               headers={'Authorization': '!'})
        _, fname = tempfile.mkstemp()
        with open(fname, 'w') as f:
            f.write(self.mock_data)

        pointer = FileStorage(open(fname, 'rb'), filename=fname,
                              content_type='application/tar+gz')
        data, headers = fm.add_file(2, pointer)
        self.assertEqual(data.identifier, 2)

    def test_upload_unauthorized(self):
        """An auth header is not included in the request."""
        fm = filemanager.FileManagementService(self.service_endpoint,
                                               headers={})
        _, fname = tempfile.mkstemp()
        with open(fname, 'w') as f:
            f.write(self.mock_data)

        pointer = FileStorage(open(fname, 'rb'), filename=fname,
                              content_type='application/tar+gz')
        with self.assertRaises(filemanager.RequestUnauthorized):
            fm.add_file(2, pointer)

    def test_upload_forbidden(self):
        """The auth token does not grant sufficient privileges."""
        fm = filemanager.FileManagementService(self.service_endpoint,
                                               headers={'Authorization': '?'})
        _, fname = tempfile.mkstemp()
        with open(fname, 'w') as f:
            f.write(self.mock_data)

        pointer = FileStorage(open(fname, 'rb'), filename=fname,
                              content_type='application/tar+gz')
        with self.assertRaises(filemanager.RequestForbidden):
            fm.add_file(2, pointer)

    def test_upload_oversize_package(self):
        """The file is too large."""
        fm = filemanager.FileManagementService(self.service_endpoint,
                                               headers={'Authorization': '!'})
        _, fname = tempfile.mkstemp()
        with open(fname, 'w') as f:
            f.write(self.mock_data * 50000)   # Bigger than arbitrary limit, above.

        pointer = FileStorage(open(fname, 'rb'), filename=fname,
                              content_type='application/tar+gz')
        with self.assertRaises(filemanager.Oversize):
            fm.add_file(2, pointer)
