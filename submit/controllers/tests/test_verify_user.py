"""Tests for :mod:`submit.controllers.verify_user`."""

from unittest import TestCase, mock
from werkzeug import MultiDict
from werkzeug.exceptions import InternalServerError
from wtforms import Form
from arxiv import status
import arxiv.submission as events
from submit.controllers.verify_user import verify_user

from pytz import timezone
from datetime import timedelta, datetime
from arxiv.users import auth, domain


class TestVerifyUser(TestCase):
    """Test behavior of :func:`.verify_user` controller."""

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
                name=domain.UserFullName("Jane", "Bloggs", "III"),
                profile=domain.UserProfile(
                    affiliation="FSU",
                    rank=3,
                    country="de",
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
    def test_get_request_with_submission(self, mock_load):
        """GET request with a submission ID."""
        submission_id = 2
        mock_load.return_value = (
            mock.MagicMock(submission_id=submission_id,
                           submitter_contact_verified=False),
            []
        )
        data, code, headers = verify_user('GET', MultiDict(), self.session,
                                          submission_id)
        self.assertEqual(code, status.HTTP_200_OK, "Returns 200 OK")
        self.assertIsInstance(data['form'], Form,
                              "Response data includes a form")

    @mock.patch('arxiv.submission.load')
    def test_post_request(self, mock_load):
        """POST request with no data."""
        submission_id = 2
        mock_load.return_value = (
            mock.MagicMock(submission_id=submission_id,
                           submitter_contact_verified=False),
            []
        )
        data, code, headers = verify_user('POST', MultiDict(), self.session,
                                          submission_id)
        self.assertEqual(code, status.HTTP_400_BAD_REQUEST,
                         "Returns 400 bad request")
        self.assertIsInstance(data['form'], Form,
                              "Response data includes a form")

    @mock.patch('submit.controllers.util.url_for')
    @mock.patch('arxiv.submission.save')
    @mock.patch('arxiv.submission.load')
    def test_post_request_with_data(self, mock_load, mock_save, mock_url_for):
        """POST request with `verify_user` set."""
        # Event store does not complain; returns object with `submission_id`.
        submission_id = 2
        mock_load.return_value = (
            mock.MagicMock(submission_id=submission_id,
                           submitter_contact_verified=False),
            []
        )
        mock_save.return_value = (
            mock.MagicMock(submission_id=submission_id,
                           submitter_contact_verified=False,),
            []
        )
        # `url_for` returns a URL (unsurprisingly).
        redirect_url = 'https://foo.bar.com/yes'
        mock_url_for.return_value = redirect_url

        form_data = MultiDict({'verify_user': 'y', 'action': 'next'})
        data, code, headers = verify_user('POST', form_data, self.session,
                                          submission_id)
        self.assertEqual(code, status.HTTP_303_SEE_OTHER,
                         "Returns 303 redirect")
        self.assertEqual(headers['Location'], redirect_url,
                         "Location for redirect is set")

    @mock.patch('submit.controllers.util.url_for')
    @mock.patch('arxiv.submission.save')
    @mock.patch('arxiv.submission.load')
    def test_verify_fails(self, mock_load, mock_save, mock_url_for):
        """Event store flakes out on authorship verification."""
        submission_id = 2
        mock_load.return_value = (
            mock.MagicMock(submission_id=submission_id,
                           submitter_contact_verified=False),
            []
        )

        # Event store does not complain; returns object with `submission_id`
        def raise_on_verify(*ev, **kwargs):
            if type(ev[0]) is events.VerifyContactInformation:
                raise events.InvalidStack([
                    events.InvalidEvent(ev[0], 'foo')
                ])
            return (
                mock.MagicMock(
                    submission_id=kwargs.get('submission_id', 2),
                    submitter_contact_verified=False,
                ),
                []
            )

        mock_save.side_effect = raise_on_verify
        form_data = MultiDict({'verify_user': 'y', 'action': 'next'})
        data, code, headers = verify_user('POST', form_data, self.session, 2)
        self.assertEqual(code, status.HTTP_400_BAD_REQUEST,
                         "Returns 400 bad request")
        self.assertIsInstance(data['form'], Form,
                              "Response data includes a form")
        self.assertIn("events", data["form"].errors,
                      "Exception messages are added to form errors.")
