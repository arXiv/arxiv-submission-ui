"""Tests for the submission system integration.

This differs from the test_workflow in that this tests the submission
system as an integrated whole from the outside via HTTP requests. This
contacts a submission system at a URL via HTTP. test_workflow.py
creates the flask app and interacts with that.

WARNING: This test is written in a very stateful manner. So the tests must be run
in order.
"""

import logging
import os
import re
import tempfile
import unittest
from urllib.parse import urlparse

import requests

from submit.factory import create_ui_web_app
from arxiv.users.helpers import generate_token
from arxiv.submission.services import classic
from arxiv.users.auth import scopes
from arxiv.users.domain import Category
from http import HTTPStatus as status
from arxiv.submission.domain.agent import User
from arxiv.submission.domain.submission import Author, SubmissionContent
from submit.tests.csrf_util import parse_csrf_token

def new_user():
    app = create_ui_web_app()
    os.environ['JWT_SECRET'] = 'foosecret'
    _, dbfile = tempfile.mkstemp(suffix='.db')
    app.config['CLASSIC_DATABASE_URI'] = f'sqlite:///{dbfile}'
    token = generate_token('1234', 'foo@bar.com', 'foouser',
                           scope=[scopes.CREATE_SUBMISSION,
                                  scopes.EDIT_SUBMISSION,
                                  scopes.VIEW_SUBMISSION,
                                  scopes.READ_UPLOAD,
                                  scopes.WRITE_UPLOAD,
                                  scopes.DELETE_UPLOAD_FILE],
                           endorsements=[
                               Category('astro-ph.GA'),
                               Category('astro-ph.CO'),
                           ])
    return (token, dbfile)


class TestSubmissionIntegration(unittest.TestCase):
    """Tests submission system."""
    @classmethod
    def setUp(self):
        self.token, self.db = new_user()
        self.headers = {'Authorization': self.token}
        self.url = 'http://localhost:8000'
        logging.basicConfig()
        self.log = logging.getLogger("LOG")

    @classmethod
    def tearDown(self):
        os.remove(self.db)
        
    def user_page(self):
        res = requests.get(self.url, headers=self.headers)
        self.log.warning(f'status was {res.status_code}')
        self.log.warning(f'status was {res.text}')
        
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers['content-type'], 'text/html; charset=utf-8')
        self.csrf = parse_csrf_token(res)


    def verify_user_page(self):
        pass

    def authorship_page(self):
        pass

    def license_page(self):
        pass

    def policy_page(self):
        pass

    def primary_page(self):
        pass

    def cross_page(self):
        pass

    def upload_page(self):
        pass

    def process_page(self):
        pass

    def metadata_page(self):
        pass

    def optional_metadata_page(self):
        pass

    def final_preview_page(self):
        pass

    def test_submission_system_basic(self):
        """Create, upload files, process TeX and submit a submission."""
        page_test_names = [
            "user_page",
            "verify_user_page",
            "authorship_page",
            "license_page",
            "policy_page",
            "primary_page",
            "cross_page",
            "upload_page",
            "process_page",
            "metadata_page",
            "optional_metadata_page",
            "final_preview_page",
        ]
        test_methods = [getattr(self, methname)
                        for methname in page_test_names]
        for page_test in test_methods:
            page_test()


if __name__ == '__main__':
    unittest.main()
