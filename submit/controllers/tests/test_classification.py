"""Tests for :mod:`submit.controllers.classification`."""

from unittest import TestCase, mock
from werkzeug import MultiDict
from werkzeug.exceptions import InternalServerError, NotFound
from wtforms import Form
from arxiv import status
import events
from submit.controllers.classification import classification, cross_list, \
    ClassificationForm


class TestClassification(TestCase):
    """Test behavior of :func:`.classification` controller."""

    @mock.patch('events.load')
    def test_get_request_with_submission(self, mock_load):
        """GET request with a submission ID."""
        submission_id = 2
        mock_load.return_value = (
            mock.MagicMock(submission_id=submission_id), []
        )
        data, code, headers = classification('GET', MultiDict(), submission_id)
        self.assertEqual(code, status.HTTP_200_OK, "Returns 200 OK")
        self.assertIsInstance(data['form'], Form,
                              "Response data includes a form")

    @mock.patch('events.load')
    def test_get_request_with_nonexistant_submission(self, mock_load):
        """GET request with a submission ID."""
        submission_id = 2

        def raise_no_such_submission(*args, **kwargs):
            raise events.exceptions.NoSuchSubmission('Nada')

        mock_load.side_effect = raise_no_such_submission
        with self.assertRaises(NotFound):
            classification('GET', MultiDict(), submission_id)

    @mock.patch('events.load')
    def test_post_request(self, mock_load):
        """POST request with no data."""
        submission_id = 2
        mock_load.return_value = (
            mock.MagicMock(submission_id=submission_id), []
        )
        data, code, headers = classification('POST', MultiDict(),
                                             submission_id)
        self.assertEqual(code, status.HTTP_400_BAD_REQUEST,
                         "Returns 400 bad request")
        self.assertIsInstance(data['form'], Form,
                              "Response data includes a form")

    @mock.patch('events.save')
    @mock.patch('events.load')
    def test_post_with_invalid_category(self, mock_load, mock_save):
        """POST request with invalid category."""
        submission_id = 2
        mock_load.return_value = (
            mock.MagicMock(submission_id=submission_id), []
        )
        mock_save.return_value = (
            mock.MagicMock(submission_id=submission_id), []
        )
        request_data = MultiDict({
            'category': 'astro-ph'  # <- expired
        })
        data, code, headers = classification('POST', request_data,
                                             submission_id)
        self.assertEqual(code, status.HTTP_400_BAD_REQUEST,
                         "Returns 400 bad request")
        self.assertIsInstance(data['form'], Form,
                              "Response data includes a form")

    @mock.patch('events.save')
    @mock.patch('events.load')
    def test_post_with_category(self, mock_load, mock_save):
        """POST request with valid category."""
        submission_id = 2
        mock_load.return_value = (
            mock.MagicMock(submission_id=submission_id), []
        )
        mock_save.return_value = (
            mock.MagicMock(submission_id=submission_id), []
        )
        request_data = MultiDict({
            'category': 'astro-ph.CO'
        })
        data, code, headers = classification('POST', request_data,
                                             submission_id)
        self.assertEqual(code, status.HTTP_200_OK, "Returns 200 OK")
        self.assertIsInstance(data['form'], Form,
                              "Response data includes a form")


class TestCrossList(TestCase):
    """Test behavior of :func:`.cross_list` controller."""

    @mock.patch('events.load')
    def test_get_request_with_submission(self, mock_load):
        """GET request with a submission ID."""
        submission_id = 2
        mock_load.return_value = (
            mock.MagicMock(
                submission_id=submission_id,
                primary_classification=mock.MagicMock(
                    category='astro-ph.EP'
                )
            ), []
        )
        data, code, headers = cross_list('GET', MultiDict(), submission_id)
        self.assertEqual(code, status.HTTP_200_OK, "Returns 200 OK")
        self.assertIsInstance(data['form'], Form,
                              "Response data includes a form")

    @mock.patch('events.load')
    def test_get_request_with_nonexistant_submission(self, mock_load):
        """GET request with a submission ID."""
        submission_id = 2

        def raise_no_such_submission(*args, **kwargs):
            raise events.exceptions.NoSuchSubmission('Nada')

        mock_load.side_effect = raise_no_such_submission
        with self.assertRaises(NotFound):
            cross_list('GET', MultiDict(), submission_id)

    @mock.patch('events.load')
    def test_post_request(self, mock_load):
        """POST request with no data."""
        submission_id = 2
        mock_load.return_value = (
            mock.MagicMock(
                submission_id=submission_id,
                primary_classification=mock.MagicMock(
                    category='astro-ph.EP'
                )
            ), []
        )
        data, code, headers = cross_list('POST', MultiDict(), submission_id)
        self.assertEqual(code, status.HTTP_400_BAD_REQUEST,
                         "Returns 400 bad request")
        self.assertIsInstance(data['form'], Form,
                              "Response data includes a form")

    @mock.patch('events.save')
    @mock.patch('events.load')
    def test_post_with_invalid_category(self, mock_load, mock_save):
        """POST request with invalid category."""
        submission_id = 2
        mock_load.return_value = (
            mock.MagicMock(
                submission_id=submission_id,
                primary_classification=mock.MagicMock(
                    category='astro-ph.EP'
                )
            ), []
        )
        mock_save.return_value = (
            mock.MagicMock(
                submission_id=submission_id,
                primary_classification=mock.MagicMock(
                    category='astro-ph.EP'
                )
            ), []
        )
        request_data = MultiDict({
            'category': 'astro-ph'  # <- expired
        })
        data, code, headers = classification('POST', request_data,
                                             submission_id)
        self.assertEqual(code, status.HTTP_400_BAD_REQUEST,
                         "Returns 400 bad request")
        self.assertIsInstance(data['form'], Form,
                              "Response data includes a form")

    @mock.patch('events.save')
    @mock.patch('events.load')
    def test_post_with_category(self, mock_load, mock_save):
        """POST request with valid category."""
        submission_id = 2
        mock_load.return_value = (
            mock.MagicMock(
                submission_id=submission_id,
                primary_classification=mock.MagicMock(
                    category='astro-ph.EP'
                )
            ), []
        )
        mock_save.return_value = (
            mock.MagicMock(
                submission_id=submission_id,
                primary_classification=mock.MagicMock(
                    category='astro-ph.EP'
                )
            ), []
        )
        request_data = MultiDict({'category': 'astro-ph.CO'})
        data, code, headers = cross_list('POST', request_data, submission_id)
        self.assertEqual(code, status.HTTP_200_OK, "Returns 200 OK")
        self.assertIsInstance(data['form'], Form,
                              "Response data includes a form")
