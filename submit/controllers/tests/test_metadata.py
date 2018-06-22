"""Tests for :mod:`submit.controllers.metadata`."""

from unittest import TestCase, mock
from werkzeug import MultiDict
from werkzeug.exceptions import InternalServerError
from wtforms import Form
from arxiv import status
from submit.controllers import metadata, optional
import events


class TestOptional(TestCase):
    """Tests for :func:`.optional`."""

    @mock.patch('events.load')
    def test_get_request_with_submission(self, mock_load):
        """GET request with a submission ID."""
        submission_id = 2
        mock_load.return_value = (
            mock.MagicMock(submission_id=submission_id), []
        )
        data, code, headers = optional('GET', MultiDict(), submission_id)
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
        data, code, headers = optional('POST', MultiDict(), submission_id)
        self.assertEqual(code, status.HTTP_200_OK, "Returns 200 OK")

        self.assertIsInstance(data['form'], Form,
                              "Response data includes a form")

    @mock.patch('events.save')
    @mock.patch('events.load')
    def test_invalid_stack_is_raised(self, mock_load, mock_save):
        """POST request results in an InvalidStack exception."""
        submission_id = 2
        mock_submission = mock.MagicMock(
            submission_id=submission_id,
            finalized=False,
            metadata=mock.MagicMock()
        )
        mock_load.return_value = (mock_submission, [])

        def raise_invalid_stack(*args, **kwargs):
            raise events.InvalidStack([])

        mock_save.side_effect = raise_invalid_stack
        request_data = MultiDict({
            'doi': '10.0001/123456',
            'journal_ref': 'foo journal 10 2010: 12-345',
            'report_num': 'foo report 12',
            'acm_class': 'F.2.2; I.2.7',
            'msc_class': '14J26'
        })
        data, code, headers = optional('POST', request_data, submission_id)
        self.assertEqual(code, status.HTTP_400_BAD_REQUEST,
                         "Returns 400 bad request")

    @mock.patch('events.save')
    @mock.patch('events.load')
    def test_save_error_is_raised(self, mock_load, mock_save):
        """POST request results in an SaveError exception."""
        submission_id = 2
        mock_submission = mock.MagicMock(
            submission_id=submission_id,
            finalized=False,
            metadata=mock.MagicMock()
        )
        mock_load.return_value = (mock_submission, [])

        def raise_save_error(*args, **kwargs):
            raise events.SaveError('nope')

        mock_save.side_effect = raise_save_error
        request_data = MultiDict({
            'doi': '10.0001/123456',
            'journal_ref': 'foo journal 10 2010: 12-345',
            'report_num': 'foo report 12',
            'acm_class': 'F.2.2; I.2.7',
            'msc_class': '14J26'
        })
        with self.assertRaises(InternalServerError):
            optional('POST', request_data, submission_id)

    @mock.patch('events.save')
    @mock.patch('events.load')
    def test_post_request_with_required_data(self, mock_load, mock_save):
        """POST request with all fields."""
        submission_id = 2
        mock_submission = mock.MagicMock(
            submission_id=submission_id,
            finalized=False,
            metadata=mock.MagicMock()
        )
        mock_load.return_value = (mock_submission, [])
        mock_save.return_value = (mock_submission, [])
        request_data = MultiDict({
            'doi': '10.0001/123456',
            'journal_ref': 'foo journal 10 2010: 12-345',
            'report_num': 'foo report 12',
            'acm_class': 'F.2.2; I.2.7',
            'msc_class': '14J26'
        })
        data, code, headers = optional('POST', request_data, submission_id)
        self.assertEqual(code, status.HTTP_200_OK, "Returns 200 OK")
        event_types = [type(ev) for ev in mock_save.call_args[0]]
        self.assertIn(events.SetDOI, event_types, "Sets submission DOI")
        self.assertIn(events.SetJournalReference, event_types,
                      "Sets journal references")
        self.assertIn(events.SetReportNumber, event_types,
                      "Sets report number")
        self.assertIn(events.SetACMClassification, event_types,
                      "Sets ACM classification")
        self.assertIn(events.SetMSCClassification, event_types,
                      "Sets MSC classification")

    @mock.patch('events.save')
    @mock.patch('events.load')
    def test_post_request_with_unchanged_data(self, mock_load, mock_save):
        """POST request with valid but unchanged data."""
        submission_id = 2
        mock_submission = mock.MagicMock(
            submission_id=submission_id,
            finalized=False,
            metadata=mock.MagicMock(**{
                'doi': '10.0001/123456',
                'journal_ref': 'foo journal 10 2010: 12-345',
                'report_num': 'foo report 12',
                'acm_class': 'F.2.2; I.2.7',
                'msc_class': '14J26'
            })
        )
        mock_load.return_value = (mock_submission, [])
        mock_save.return_value = (mock_submission, [])
        request_data = MultiDict({
            'doi': '10.0001/123456',
            'journal_ref': 'foo journal 10 2010: 12-345',
            'report_num': 'foo report 12',
            'acm_class': 'F.2.2; I.2.7',
            'msc_class': '14J26'
        })
        data, code, headers = optional('POST', request_data, submission_id)
        self.assertEqual(code, status.HTTP_200_OK, "Returns 200 OK")
        self.assertEqual(mock_save.call_count, 0, "No events are generated")

    @mock.patch('events.save')
    @mock.patch('events.load')
    def test_post_request_with_some_changes(self, mock_load, mock_save):
        """POST request with only some changed data."""
        submission_id = 2
        mock_submission = mock.MagicMock(
            submission_id=submission_id,
            finalized=False,
            metadata=mock.MagicMock(**{
                'doi': '10.0001/123456',
                'journal_ref': 'foo journal 10 2010: 12-345',
                'report_num': 'foo report 12',
                'acm_class': 'F.2.2; I.2.7',
                'msc_class': '14J26'
            })
        )
        mock_load.return_value = (mock_submission, [])
        mock_save.return_value = (mock_submission, [])
        request_data = MultiDict({
            'doi': '10.0001/123456',
            'journal_ref': 'foo journal 10 2010: 12-345',
            'report_num': 'foo report 13',
            'acm_class': 'F.2.2; I.2.7',
            'msc_class': '14J27'
        })
        data, code, headers = optional('POST', request_data, submission_id)
        self.assertEqual(code, status.HTTP_200_OK, "Returns 200 OK")
        self.assertEqual(mock_save.call_count, 1, "Events are generated")
        event_types = [type(ev) for ev in mock_save.call_args[0]]
        self.assertIn(events.SetReportNumber, event_types,
                      "Sets report number")
        self.assertIn(events.SetMSCClassification, event_types,
                      "Sets MSC classification")
        self.assertEqual(len(event_types), 2, "Only two events are generated")


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

    @mock.patch('events.save')
    @mock.patch('events.load')
    def test_post_request_with_required_data(self, mock_load, mock_save):
        """POST request with title, abstract, and author names."""
        submission_id = 2
        mock_submission = mock.MagicMock(
            submission_id=submission_id,
            finalized=False,
            metadata=mock.MagicMock(
                title='the old title',
                abstract='not the abstract that you are looking for',
                authors_display='bloggs, j'
            )
        )
        mock_load.return_value = (mock_submission, [])
        mock_save.return_value = (mock_submission, [])
        request_data = MultiDict({
            'title': 'a new, valid title',
            'abstract': 'this abstract is at least twenty characters long',
            'authors_display': 'j doe, j bloggs'
        })
        data, code, headers = metadata('POST', request_data, submission_id)
        self.assertEqual(code, status.HTTP_200_OK, "Returns 200 OK")
        event_types = [type(ev) for ev in mock_save.call_args[0]]
        self.assertIn(events.SetTitle, event_types, "Sets submission title")
        self.assertIn(events.SetAbstract, event_types,
                      "Sets submission abstract")
        self.assertIn(events.UpdateAuthors, event_types,
                      "Sets submission authors")

    @mock.patch('events.save')
    @mock.patch('events.load')
    def test_post_request_with_unchanged_data(self, mock_load, mock_save):
        """POST request with valid but unaltered data."""
        submission_id = 2
        mock_submission = mock.MagicMock(
            submission_id=submission_id,
            finalized=False,
            metadata=mock.MagicMock(
                title='the old title',
                abstract='not the abstract that you are looking for',
                authors_display='bloggs, j'
            )
        )
        mock_load.return_value = (mock_submission, [])
        mock_save.return_value = (mock_submission, [])
        request_data = MultiDict({
            'title': 'the old title',
            'abstract': 'not the abstract that you are looking for',
            'authors_display': 'bloggs, j'
        })
        data, code, headers = metadata('POST', request_data, submission_id)
        self.assertEqual(code, status.HTTP_200_OK, "Returns 200 OK")
        self.assertEqual(mock_save.call_count, 0, "No events are generated")

    @mock.patch('events.save')
    @mock.patch('events.load')
    def test_post_request_some_changed_data(self, mock_load, mock_save):
        """POST request with valid data; only the title has changed."""
        submission_id = 2
        mock_submission = mock.MagicMock(
            submission_id=submission_id,
            finalized=False,
            metadata=mock.MagicMock(
                title='the old title',
                abstract='not the abstract that you are looking for',
                authors_display='bloggs, j'
            )
        )
        mock_load.return_value = (mock_submission, [])
        mock_save.return_value = (mock_submission, [])
        request_data = MultiDict({
            'title': 'the new title',
            'abstract': 'not the abstract that you are looking for',
            'authors_display': 'bloggs, j'
        })
        data, code, headers = metadata('POST', request_data, submission_id)
        self.assertEqual(code, status.HTTP_200_OK, "Returns 200 OK")
        self.assertEqual(mock_save.call_count, 1, "One event is generated")
        self.assertIsInstance(mock_save.call_args[0][0], events.SetTitle,
                              "SetTitle event is generated")

    @mock.patch('events.save')
    @mock.patch('events.load')
    def test_post_request_invalid_data(self, mock_load, mock_save):
        """POST request with invalid data."""
        submission_id = 2
        mock_submission = mock.MagicMock(
            submission_id=submission_id,
            finalized=False,
            metadata=mock.MagicMock(
                title='the old title',
                abstract='not the abstract that you are looking for',
                authors_display='bloggs, j'
            )
        )
        mock_load.return_value = (mock_submission, [])
        mock_save.return_value = (mock_submission, [])
        request_data = MultiDict({
            'title': 'the new title',
            'abstract': 'too short',
            'authors_display': 'bloggs, j'
        })
        data, code, headers = metadata('POST', request_data, submission_id)
        self.assertEqual(code, status.HTTP_400_BAD_REQUEST,
                         "Returns 400 bad request")
        self.assertIsInstance(data['form'], Form,
                              "Response data includes a form")
        self.assertIn('abstract', data['form'].errors,
                      'Validation errors are added to the form')

    @mock.patch('events.save')
    @mock.patch('events.load')
    def test_invalid_stack_is_raised(self, mock_load, mock_save):
        """POST request results in an InvalidStack exception."""
        submission_id = 2
        mock_submission = mock.MagicMock(
            submission_id=submission_id,
            finalized=False,
            metadata=mock.MagicMock(
                title='the old title',
                abstract='not the abstract that you are looking for',
                authors_display='bloggs, j'
            )
        )
        mock_load.return_value = (mock_submission, [])

        def raise_invalid_stack(*args, **kwargs):
            raise events.InvalidStack([])

        mock_save.side_effect = raise_invalid_stack

        request_data = MultiDict({
            'title': 'a new, valid title',
            'abstract': 'this abstract is at least twenty characters long',
            'authors_display': 'j doe, j bloggs'
        })
        data, code, headers = metadata('POST', request_data, submission_id)
        self.assertEqual(code, status.HTTP_400_BAD_REQUEST,
                         "Returns 400 bad request")

    @mock.patch('events.save')
    @mock.patch('events.load')
    def test_save_error_is_raised(self, mock_load, mock_save):
        """POST request results in an SaveError exception."""
        submission_id = 2
        mock_submission = mock.MagicMock(
            submission_id=submission_id,
            finalized=False,
            metadata=mock.MagicMock(
                title='the old title',
                abstract='not the abstract that you are looking for',
                authors_display='bloggs, j'
            )
        )
        mock_load.return_value = (mock_submission, [])

        def raise_save_error(*args, **kwargs):
            raise events.SaveError('nope')

        mock_save.side_effect = raise_save_error
        request_data = MultiDict({
            'title': 'a new, valid title',
            'abstract': 'this abstract is at least twenty characters long',
            'authors_display': 'j doe, j bloggs'
        })
        with self.assertRaises(InternalServerError):
            metadata('POST', request_data, submission_id)
