"""Tests for the submission application as a whole."""

import os
import re
import tempfile
from unittest import TestCase
from urllib.parse import urlparse

from submit.factory import create_ui_web_app
from arxiv.users.helpers import generate_token
from arxiv.submission.services import classic
from arxiv.users.auth import scopes
from arxiv.users.domain import Category
from arxiv import status

CSRF_PATTERN = (r'\<input id="csrf_token" name="csrf_token" type="hidden"'
                r' value="([^\"]+)">')


class TestSubmissionWorkflow(TestCase):
    """Tests that progress through the submission workflow in various ways."""

    def setUp(self):
        """Create an application instance."""
        self.app = create_ui_web_app()
        os.environ['JWT_SECRET'] = self.app.config.get('JWT_SECRET')
        _, self.db = tempfile.mkstemp(suffix='.db')
        self.app.config['CLASSIC_DATABASE_URI'] = f'sqlite:///{self.db}'
        self.token = generate_token('1234', 'foo@bar.com', 'foouser',
                                    scope=[scopes.CREATE_SUBMISSION,
                                           scopes.EDIT_SUBMISSION,
                                           scopes.VIEW_SUBMISSION,
                                           scopes.READ_UPLOAD,
                                           scopes.WRITE_UPLOAD,
                                           scopes.DELETE_UPLOAD_FILE],
                                    endorsements=[
                                        Category('astro-ph', 'GA'),
                                        Category('astro-ph', 'CO'),
                                    ])
        self.headers = {'Authorization': self.token}
        self.client = self.app.test_client()
        with self.app.app_context():
            classic.create_all()

    def tearDown(self):
        """Remove the temporary database."""
        os.remove(self.db)

    def _parse_csrf_token(self, response):
        try:
            match = re.search(CSRF_PATTERN, response.data.decode('utf-8'))
            token = match.group(1)
        except AttributeError:
            self.fail('Could not find CSRF token')
        return token

    def test_create_submission(self):
        """User creates a new submission."""
        # Get the submission creation page.
        response = self.client.get('/', headers=self.headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.content_type, 'text/html; charset=utf-8')
        self.assertIn(b'Submit an Article', response.data)
        token = self._parse_csrf_token(response)

        # Create a submission.
        response = self.client.post('/',
                                    data={'new': 'new',
                                          'csrf_token': token},
                                    headers=self.headers)
        self.assertEqual(response.status_code, status.HTTP_303_SEE_OTHER)

        # Get the next page in the process. This should be the verify_user
        # stage.
        next_page = urlparse(response.headers['Location'])
        self.assertIn('verify_user', next_page.path)
        response = self.client.get(next_page.path, headers=self.headers)
        self.assertIn(
            b'By checking this box, I verify that my user information is'
            b' correct.',
            response.data
        )
        token = self._parse_csrf_token(response)

        # Submit the verify user page.
        response = self.client.post(next_page.path,
                                    data={'verify_user': 'y',
                                          'action': 'next',
                                          'csrf_token': token},
                                    headers=self.headers)
        self.assertEqual(response.status_code, status.HTTP_303_SEE_OTHER)

        # Get the next page in the process. This is the authorship stage.
        next_page = urlparse(response.headers['Location'])
        self.assertIn('authorship', next_page.path)
        response = self.client.get(next_page.path, headers=self.headers)
        self.assertIn(b'I am an author of this paper', response.data)
        token = self._parse_csrf_token(response)

        # Submit the authorship page.
        response = self.client.post(next_page.path,
                                    data={'authorship': 'y',
                                          'action': 'next',
                                          'csrf_token': token},
                                    headers=self.headers)
        self.assertEqual(response.status_code, status.HTTP_303_SEE_OTHER)

        # Get the next page in the process. This is the license stage.
        next_page = urlparse(response.headers['Location'])
        self.assertIn('license', next_page.path)
        response = self.client.get(next_page.path, headers=self.headers)
        self.assertIn(b'Select a license', response.data)
        token = self._parse_csrf_token(response)

        # Submit the license page.
        selected = "http://creativecommons.org/licenses/by-sa/4.0/"
        response = self.client.post(next_page.path,
                                    data={'license': selected,
                                          'action': 'next',
                                          'csrf_token': token},
                                    headers=self.headers)
        self.assertEqual(response.status_code, status.HTTP_303_SEE_OTHER)

        # Get the next page in the process. This is the policy stage.
        next_page = urlparse(response.headers['Location'])
        self.assertIn('policy', next_page.path)
        response = self.client.get(next_page.path, headers=self.headers)
        self.assertIn(
            b'By checking this box, I agree to the policies listed on'
            b' this page',
            response.data
        )
        token = self._parse_csrf_token(response)

        # Submit the policy page.
        response = self.client.post(next_page.path,
                                    data={'policy': 'y',
                                          'action': 'next',
                                          'csrf_token': token},
                                    headers=self.headers)
        self.assertEqual(response.status_code, status.HTTP_303_SEE_OTHER)

        # Get the next page in the process. This is the primary category stage.
        next_page = urlparse(response.headers['Location'])
        self.assertIn('classification', next_page.path)
        response = self.client.get(next_page.path, headers=self.headers)
        self.assertIn(b'Choose a primary classification', response.data)
        token = self._parse_csrf_token(response)

        # Submit the primary category page.
        response = self.client.post(next_page.path,
                                    data={'category': 'astro-ph.GA',
                                          'action': 'next',
                                          'csrf_token': token},
                                    headers=self.headers)
        self.assertEqual(response.status_code, status.HTTP_303_SEE_OTHER)

        # Get the next page in the process. This is the cross list stage.
        next_page = urlparse(response.headers['Location'])
        self.assertIn('cross_list', next_page.path)
        response = self.client.get(next_page.path, headers=self.headers)
        self.assertIn(b'Choose cross-list classifications', response.data)
        token = self._parse_csrf_token(response)

        # Submit the cross-list category page.
        response = self.client.post(next_page.path,
                                    data={'category': 'astro-ph.CO',
                                          'action': 'next',
                                          'csrf_token': token},
                                    headers=self.headers)
        self.assertEqual(response.status_code, status.HTTP_303_SEE_OTHER)

        # Get the next page in the process. This is the file upload stage.
        next_page = urlparse(response.headers['Location'])
        self.assertIn('file_upload', next_page.path)
        response = self.client.get(next_page.path, headers=self.headers)
        self.assertIn(b'Upload files', response.data)
        token = self._parse_csrf_token(response)
