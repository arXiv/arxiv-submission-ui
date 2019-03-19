"""Tests for :mod:`submit.controllers.classification`."""

from unittest import TestCase, mock
from werkzeug import MultiDict
from werkzeug.exceptions import InternalServerError, NotFound, BadRequest
from wtforms import Form
from http import HTTPStatus as status
import arxiv.submission as events
from submit.controllers import classification

from pytz import timezone
from datetime import timedelta, datetime
from arxiv.users import auth, domain


class TestSetPrimaryClassification(TestCase):
    """Test behavior of :func:`.classification` controller."""

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
                    default_category=domain.Category('astro-ph.GA'),
                    submission_groups=['grp_physics']
                )
            ),
            authorizations=domain.Authorizations(
                scopes=[auth.scopes.CREATE_SUBMISSION,
                        auth.scopes.EDIT_SUBMISSION,
                        auth.scopes.VIEW_SUBMISSION],
                endorsements=[domain.Category('astro-ph.CO'),
                              domain.Category('astro-ph.GA')]
            )
        )

    @mock.patch(f'{classification.__name__}.ClassificationForm.Meta.csrf',
                False)
    @mock.patch('arxiv.submission.load')
    def test_get_request_with_submission(self, mock_load):
        """GET request with a submission ID."""
        submission_id = 2
        before = mock.MagicMock(submission_id=submission_id, published=False,
                                arxiv_id=None, submitter_is_author=False,
                                finalized=False, version=1)
        mock_load.return_value = (before, [])
        params = MultiDict()
        data, code, _ = classification.classification('GET', params,
                                                      self.session,
                                                      submission_id)
        self.assertEqual(code, status.OK, "Returns 200 OK")
        self.assertIsInstance(data['form'], Form, "Data includes a form")

    @mock.patch(f'{classification.__name__}.ClassificationForm.Meta.csrf',
                False)
    @mock.patch('arxiv.submission.load')
    def test_get_request_with_nonexistant_submission(self, mock_load):
        """GET request with a submission ID."""
        submission_id = 2

        def raise_no_such_submission(*args, **kwargs):
            raise events.exceptions.NoSuchSubmission('Nada')

        mock_load.side_effect = raise_no_such_submission
        with self.assertRaises(NotFound):
            classification.classification('GET', MultiDict(), self.session,
                                          submission_id)

    @mock.patch(f'{classification.__name__}.ClassificationForm.Meta.csrf',
                False)
    @mock.patch('arxiv.submission.load')
    def test_post_request(self, mock_load):
        """POST request with no data."""
        submission_id = 2
        before = mock.MagicMock(submission_id=submission_id, published=False,
                                arxiv_id=None, submitter_is_author=False,
                                finalized=False, version=1)
        mock_load.return_value = (before, [])
        try:
            classification.classification('POST', MultiDict(), self.session,
                                          submission_id)
            self.fail('BadRequest not raised')
        except BadRequest as e:
            data = e.description
            self.assertIsInstance(data['form'], Form, "Data includes a form")

    @mock.patch(f'{classification.__name__}.ClassificationForm.Meta.csrf',
                False)
    @mock.patch('submit.controllers.util.url_for')
    @mock.patch(f'{classification.__name__}.save')
    @mock.patch('arxiv.submission.load')
    def test_post_request_with_data(self, mock_load, mock_save, mock_url_for):
        """POST request with `classification` set."""
        # Event store does not complain; returns object with `submission_id`.
        submission_id = 2
        before = mock.MagicMock(submission_id=submission_id, published=False,
                                arxiv_id=None, submitter_is_author=False,
                                finalized=False, version=1)
        mock_clsn = mock.MagicMock(category='astro-ph.CO')
        after = mock.MagicMock(submission_id=submission_id, published=False,
                               arxiv_id=None, submitter_is_author=False,
                               primary_classification=mock_clsn,
                               finalized=False, version=1)
        mock_load.return_value = (before, [])
        mock_save.return_value = (after, [])
        mock_url_for.return_value = 'https://foo.bar.com/yes'

        params = MultiDict({'category': 'astro-ph.CO', 'action': 'next'})
        _, code, _ = classification.classification('POST', params,
                                                   self.session, submission_id)
        self.assertEqual(code, status.SEE_OTHER, "Returns redirect")

    @mock.patch(f'{classification.__name__}.ClassificationForm.Meta.csrf',
                False)
    @mock.patch('submit.controllers.util.url_for')
    @mock.patch(f'{classification.__name__}.save')
    @mock.patch('arxiv.submission.load')
    def test_save_error(self, mock_load, mock_save, mock_url_for):
        """Event store flakes out on saving classification event."""
        submission_id = 2
        before = mock.MagicMock(submission_id=submission_id, published=False,
                                arxiv_id=None, submitter_is_author=False,
                                finalized=False, version=1)
        mock_load.return_value = (before, [])

        # Event store does not complain; returns object with `submission_id`
        def raise_on_set(*ev, **kwargs):
            if type(ev[0]) is events.SetPrimaryClassification:
                raise events.SaveError('never get back')
            ident = kwargs.get('submission_id', 2)
            return (mock.MagicMock(submission_id=ident), [])

        mock_save.side_effect = raise_on_set
        params = MultiDict({'category': 'astro-ph.CO', 'action': 'next'})
        try:
            classification.classification('POST', params, self.session, 2)
            self.fail('InternalServerError not raised')
        except InternalServerError as e:
            data = e.description
            self.assertIsInstance(data['form'], Form, "Data includes a form")
