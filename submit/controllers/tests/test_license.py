"""Tests for :mod:`submit.controllers.license`."""

from unittest import TestCase, mock
from werkzeug import MultiDict
from werkzeug.exceptions import InternalServerError, NotFound
from wtforms import Form
from arxiv import status
import events
from submit.controllers.license import license, LicenseForm


class TestVerifyUser(TestCase):
    """Test behavior of :func:`.license` controller."""

    @mock.patch('events.load')
    def test_get_request_with_submission(self, mock_load):
        """GET request with a submission ID."""
        submission_id = 2
        mock_load.return_value = (
            mock.MagicMock(submission_id=submission_id), []
        )
        data, code, headers = license('GET', MultiDict(), submission_id)
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
            license('GET', MultiDict(), submission_id)

    @mock.patch('events.load')
    def test_post_request(self, mock_load):
        """POST request with no data."""
        submission_id = 2
        mock_load.return_value = (
            mock.MagicMock(submission_id=submission_id), []
        )
        data, code, headers = license('POST', MultiDict(), submission_id)
        self.assertEqual(code, status.HTTP_400_BAD_REQUEST,
                         "Returns 400 bad request")
        self.assertIsInstance(data['form'], Form,
                              "Response data includes a form")

    @mock.patch('submit.controllers.util.url_for')
    @mock.patch('events.save')
    @mock.patch('events.load')
    def test_post_request_with_data(self, mock_load, mock_save, mock_url_for):
        """POST request with `license` set."""
        # Event store does not complain; returns object with `submission_id`.
        submission_id = 2
        mock_load.return_value = (
            mock.MagicMock(submission_id=submission_id), []
        )
        mock_save.return_value = (
            mock.MagicMock(submission_id=submission_id), []
        )
        # `url_for` returns a URL (unsurprisingly).
        redirect_url = 'https://foo.bar.com/yes'
        mock_url_for.return_value = redirect_url

        form_data = MultiDict({
            'license': 'http://arxiv.org/licenses/nonexclusive-distrib/1.0/',
            'action': 'next'
        })
        data, code, headers = license('POST', form_data, submission_id)
        self.assertEqual(code, status.HTTP_303_SEE_OTHER,
                         "Returns 303 redirect")
        self.assertEqual(headers['Location'], redirect_url,
                         "Location for redirect is set")

    @mock.patch('submit.controllers.util.url_for')
    @mock.patch('events.save')
    @mock.patch('events.load')
    def test_select_fails(self, mock_load, mock_save, mock_url_for):
        """Event store flakes out on license selection."""
        submission_id = 2
        mock_load.return_value = (
            mock.MagicMock(submission_id=submission_id), []
        )

        # Event store does not complain; returns object with `submission_id`
        def raise_on_verify(*ev, **kwargs):
            if type(ev[0]) is events.SelectLicense:
                raise events.InvalidStack([
                    events.InvalidEvent(ev[0], 'foo')
                ])
            return (
                mock.MagicMock(submission_id=kwargs.get('submission_id', 2)),
                []
            )

        mock_save.side_effect = raise_on_verify
        form_data = MultiDict({
            'license': 'http://arxiv.org/licenses/nonexclusive-distrib/1.0/',
            'action': 'next'
        })
        data, code, headers = license('POST', form_data, 2)
        self.assertEqual(code, status.HTTP_400_BAD_REQUEST,
                         "Returns 400 bad request")
        self.assertIsInstance(data['form'], Form,
                              "Response data includes a form")
        self.assertIn("events", data["form"].errors,
                      "Exception messages are added to form errors.")
