"""Tests for the submission UI domain classes."""

from unittest import TestCase, mock
from datetime import datetime
from arxiv.submission.domain import Submission, User
from .. import domain


class TestSubmissionStage(TestCase):
    """Tests for :class:`domain.SubmissionStage`."""

    def test_initial_stage(self):
        """Nothing has been done yet."""
        submission = Submission(
            creator=User('12345', 'foo@user.edu'),
            owner=User('12345', 'foo@user.edu'),
            created=datetime.now()
        )
        submission_stage = domain.SubmissionStage(submission)
        self.assertEqual(submission_stage.current_stage,
                         domain.SubmissionStage.ORDER[0][0],
                         "The current stage is the first stage.")
        self.assertEqual(submission_stage.next_stage,
                         domain.SubmissionStage.ORDER[1][0],
                         "The next stage is the second stage.")
        self.assertIsNone(submission_stage.previous_stage,
                          "There is no previous stage.")

        self.assertTrue(submission_stage.before(domain.SubmissionStage.POLICY))
        self.assertTrue(
            submission_stage.on_or_before(domain.SubmissionStage.POLICY)
        )
        self.assertTrue(
            submission_stage.on_or_before(submission_stage.current_stage)
        )
        self.assertFalse(submission_stage.after(domain.SubmissionStage.POLICY))
        self.assertFalse(
            submission_stage.on_or_after(domain.SubmissionStage.POLICY)
        )
        self.assertTrue(
            submission_stage.on_or_after(submission_stage.current_stage)
        )

    def test_verify_user(self):
        """The user has verified their information."""
        submission = Submission(
            creator=User('12345', 'foo@user.edu'),
            owner=User('12345', 'foo@user.edu'),
            created=datetime.now(),
            submitter_contact_verified=True
        )
        submission_stage = domain.SubmissionStage(submission)
        self.assertEqual(submission_stage.previous_stage,
                         domain.SubmissionStage.VERIFY_USER,
                         "The verify user stage is complete.")
        self.assertEqual(submission_stage.next_stage,
                         domain.SubmissionStage.LICENSE,
                         "The next stage is to select license.")
        self.assertEqual(submission_stage.current_stage,
                         domain.SubmissionStage.AUTHORSHIP,
                         "The current stage is to confirm authorship.")
