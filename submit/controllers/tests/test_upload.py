"""Tests for :mod:`submit.controllers.upload`."""

from unittest import TestCase, mock

from pytz import timezone
from datetime import timedelta, datetime
from werkzeug import MultiDict

from arxiv import status
from arxiv.users import auth, domain
from arxiv.submission.domain.submission import SubmissionContent
from submit.domain import UploadStatus, FileStatus, Error
from submit.services import filemanager
from .. import upload


class TestUpload(TestCase):
    """Tests for :func:`submit.controllers.upload.upload`."""

    def setUp(self):
        """Create an authenticated session."""
        # Specify the validity period for the session.
        start = datetime.now(tz=timezone('US/Eastern'))
        end = start + timedelta(seconds=36000)
        self.session = domain.Session(
            session_id='123-session-abc',
            start_time=start, end_time=end,
            user=domain.User(
                user_id='235678',
                email='foo@foo.com',
                username='foouser',
                name=domain.UserFullName('Jane', 'Bloggs', 'III'),
                profile=domain.UserProfile(
                    affiliation='FSU',
                    rank=3,
                    country='de',
                    default_category=domain.Category('astro-ph', 'GA'),
                    submission_groups=['grp_physics']
                )
            ),
            authorizations=domain.Authorizations(
                scopes=[auth.scopes.CREATE_SUBMISSION,
                        auth.scopes.EDIT_SUBMISSION,
                        auth.scopes.VIEW_SUBMISSION],
                endorsements=[domain.Category('astro-ph', 'CO'),
                              domain.Category('astro-ph', 'GA')]
            )
        )

    @mock.patch('arxiv.submission.load')
    def test_get_no_upload(self, mock_load):
        """GET request for submission with no upload package."""
        submission_id = 2
        mock_submission = mock.MagicMock(
            submission_id=submission_id,
            source_content=None
        )
        mock_load.return_value = (
            mock_submission, []
        )
        params = MultiDict({})
        files = MultiDict({})
        response_data, code, headers = upload.upload(
            'GET', params, files, self.session, submission_id
        )
        self.assertEqual(code, status.HTTP_200_OK, 'Returns 200 OK')
        self.assertIn('submission', response_data, 'Submission is in response')
        self.assertIn('submission_id', response_data, 'ID is in response')

    @mock.patch(f'{upload.__name__}.filemanager')
    @mock.patch('arxiv.submission.load')
    def test_get_upload(self, mock_load, mock_filemanager):
        """GET request for submission with an existing upload package."""
        mock_filemanager.RequestFailed = filemanager.RequestFailed
        submission_id = 2
        mock_load.return_value = (
            mock.MagicMock(
                submission_id=submission_id,
                source_content=SubmissionContent(
                    identifier='5433',
                    checksum='a1s2d3f4',
                    size=593920,
                    format=''
                )
            ), []
        )
        mock_filemanager.get_upload_status.return_value = (
            UploadStatus(
                identifier=25,
                checksum='a1s2d3f4',
                size=593920,
                file_list=[FileStatus(
                    path='',
                    name='thebestfile.pdf',
                    file_type='PDF',
                    added=datetime.now(),
                    size=20505,
                    ancillary=False,
                    errors=[]
                )],
                errors=[]
            ), {}
        )
        params = MultiDict({})
        files = MultiDict({})
        response_data, code, headers = upload.upload(
            'GET', params, files, self.session, submission_id
        )
        self.assertEqual(code, status.HTTP_200_OK, 'Returns 200 OK')
        self.assertEqual(mock_filemanager.get_upload_status.call_count, 1,
                         'Calls the file management service')
        self.assertIn('status', response_data, 'Upload status is in response')
        self.assertIn('submission', response_data, 'Submission is in response')
        self.assertIn('submission_id', response_data, 'ID is in response')

    @mock.patch(f'{upload.__name__}.filemanager')
    @mock.patch(f'{upload.__name__}.save')
    @mock.patch(f'arxiv.submission.load')
    def test_post_upload(self, mock_load, mock_save, mock_filemanager):
        """POST request for submission with an existing upload package."""
        mock_filemanager.RequestFailed = filemanager.RequestFailed
        submission_id = 2
        mock_submission = mock.MagicMock(
            submission_id=submission_id,
            source_content=SubmissionContent(
                identifier='5433',
                checksum='a1s2d3f4',
                size=593920,
                format=''
            )
        )
        mock_load.return_value = (mock_submission, [])
        mock_save.return_value = (mock_submission, [])
        mock_filemanager.add_file.return_value = (
            UploadStatus(
                identifier=25,
                checksum='a1s2d3f4',
                size=593920,
                file_list=[FileStatus(
                    path='',
                    name='thebestfile.pdf',
                    file_type='PDF',
                    added=datetime.now(),
                    size=20505,
                    ancillary=False,
                    errors=[]
                )],
                errors=[]
            ), {}
        )
        params = MultiDict({})
        mock_file = mock.MagicMock()
        files = MultiDict({'file': mock_file})
        response_data, code, headers = upload.upload(
            'POST', params, files, self.session, submission_id
        )
        self.assertEqual(code, status.HTTP_200_OK, 'Returns 200 OK')
        self.assertEqual(mock_filemanager.add_file.call_count, 1,
                         'Calls the file management service')
        self.assertIn('status', response_data, 'Upload status is in response')
        self.assertIn('submission', response_data, 'Submission is in response')
        self.assertIn('submission_id', response_data, 'ID is in response')
        self.assertTrue(mock_filemanager.add_file.called_with(mock_file))


class TestDelete(TestCase):
    """Tests for :func:`submit.controllers.upload.delete`."""

    def setUp(self):
        """Create an authenticated session."""
        # Specify the validity period for the session.
        start = datetime.now(tz=timezone('US/Eastern'))
        end = start + timedelta(seconds=36000)
        self.session = domain.Session(
            session_id='123-session-abc',
            start_time=start, end_time=end,
            user=domain.User(
                user_id='235678',
                email='foo@foo.com',
                username='foouser',
                name=domain.UserFullName('Jane', 'Bloggs', 'III'),
                profile=domain.UserProfile(
                    affiliation='FSU',
                    rank=3,
                    country='de',
                    default_category=domain.Category('astro-ph', 'GA'),
                    submission_groups=['grp_physics']
                )
            ),
            authorizations=domain.Authorizations(
                scopes=[auth.scopes.CREATE_SUBMISSION,
                        auth.scopes.EDIT_SUBMISSION,
                        auth.scopes.VIEW_SUBMISSION],
                endorsements=[domain.Category('astro-ph', 'CO'),
                              domain.Category('astro-ph', 'GA')]
            )
        )

    @mock.patch(f'{upload.__name__}.filemanager')
    @mock.patch('arxiv.submission.load')
    def test_get_delete(self, mock_load, mock_filemanager):
        """GET request to delete a file."""
        mock_filemanager.RequestFailed = filemanager.RequestFailed
        submission_id = 2
        mock_load.return_value = (
            mock.MagicMock(
                submission_id=submission_id,
                source_content=SubmissionContent(
                    identifier='5433',
                    checksum='a1s2d3f4',
                    size=593920,
                    format=''
                )
            ), []
        )
        file_path = 'anc/foo.jpeg'
        params = MultiDict({'file_path': file_path})
        response_data, code, headers = upload.delete(
            'GET', params, self.session, submission_id
        )
        self.assertEqual(code, status.HTTP_200_OK, "Returns 200 OK")
        self.assertIn('form', response_data, "Returns a form in response")
        self.assertEqual(response_data['form'].file_path.data, file_path,
                         'File path is set on the form')

    @mock.patch(f'{upload.__name__}.filemanager')
    @mock.patch('arxiv.submission.load')
    def test_post_delete(self, mock_load, mock_filemanager):
        """POST request to delete a file without confirmation."""
        mock_filemanager.RequestFailed = filemanager.RequestFailed
        submission_id = 2
        mock_load.return_value = (
            mock.MagicMock(
                submission_id=submission_id,
                source_content=SubmissionContent(
                    identifier='5433',
                    checksum='a1s2d3f4',
                    size=593920,
                    format=''
                )
            ), []
        )
        file_path = 'anc/foo.jpeg'
        params = MultiDict({'file_path': file_path})
        response_data, code, headers = upload.delete(
            'POST', params, self.session, submission_id
        )
        self.assertEqual(code, status.HTTP_400_BAD_REQUEST,
                         "Returns 400 Bad Request")
        self.assertIn('form', response_data, "Returns a form in response")
        self.assertEqual(response_data['form'].file_path.data, file_path,
                         'File path is set on the form')

    @mock.patch(f'{upload.__name__}.url_for')
    @mock.patch(f'{upload.__name__}.filemanager')
    @mock.patch('arxiv.submission.load')
    def test_post_delete_confirmed(self, mock_load, mock_filemanager,
                                   mock_url_for):
        """POST request to delete a file without confirmation."""
        redirect_uri = '/foo'
        mock_url_for.return_value = redirect_uri
        mock_filemanager.RequestFailed = filemanager.RequestFailed
        upload_id = '5433'
        submission_id = 2
        mock_load.return_value = (
            mock.MagicMock(
                submission_id=submission_id,
                source_content=SubmissionContent(
                    identifier=upload_id,
                    checksum='a1s2d3f4',
                    size=593920,
                    format=''
                )
            ), []
        )
        file_path = 'anc/foo.jpeg'
        params = MultiDict({'file_path': file_path, 'confirmed': True})
        response_data, code, headers = upload.delete(
            'POST', params, self.session, submission_id
        )
        self.assertTrue(
            mock_filemanager.delete_file.called_with(upload_id, file_path),
            "Delete file method of file manager service is called"
        )
        self.assertEqual(code, status.HTTP_303_SEE_OTHER,
                         "Returns 303 See Other")
        self.assertEqual(headers['Location'], redirect_uri,
                         "Returns redirect URI in Location header")