"""Tests for :mod:`submit.controllers.metadata`."""

from unittest import TestCase, mock
from werkzeug import MultiDict
from wtforms import Form
from arxiv import status
from submit.controllers import metadata, optional


class TestMetadata(TestCase):
    """Tests for :func:`.metadata`."""

    @mock.patch('events.load')
    def test_get_request_with_submission(self, mock_load):
        """GET request with a submission ID."""
        submission_id = 2
        mock_load.return_value = (
            mock.MagicMock(submission_id=submission_id), []
        )
        data, code, headers = metadata('GET', MultiDict(), submission_id)
        self.assertEqual(code, status.HTTP_200_OK, "Returns 200 OK")
        self.assertIsInstance(data['form'], Form,
                              "Response data includes a form")

    @mock.patch('events.load')
    def test_post_request_with_no_data(self, mock_load):
        """POST request has no form data."""
        submission_id = 2
        mock_load.return_value = (
            mock.MagicMock(submission_id=submission_id), []
        )
        data, code, headers = metadata('POST', MultiDict(), submission_id)
        self.assertEqual(code, status.HTTP_400_BAD_REQUEST,
                         "Returns 400 bad request")
        self.assertIsInstance(data['form'], Form,
                              "Response data includes a form")
