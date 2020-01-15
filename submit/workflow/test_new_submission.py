"""Tests for workflow"""

from unittest import TestCase, mock
from submit import workflow
from submit.workflow import processor
from arxiv.submission.domain.event import CreateSubmission
from arxiv.submission.domain.agent import User
from submit.workflow.stages import *


class TestNewSubmissionWorkflow(TestCase):

    def testWorkflowGetitem(self):
        wf = workflow.WorkflowDefinition(
            order=[VerifyUser(), Policy(), FinalPreview()])

        self.assertIsNotNone(wf[VerifyUser])
        self.assertEqual(wf[VerifyUser].__class__, VerifyUser)
        self.assertEqual(wf[0].__class__, VerifyUser)

        self.assertEqual(wf[VerifyUser], wf[0])
        self.assertEqual(wf[VerifyUser], wf['VerifyUser'])
        self.assertEqual(wf[VerifyUser], wf['verify_user'])
        self.assertEqual(wf[VerifyUser], wf[wf.order[0]])

        self.assertEqual(next(wf.iter_prior(wf[Policy])), wf[VerifyUser])

    def testVerifyUser(self):
        seen = {}
        submitter = User('Bob', 'FakePants', 'Sponge',
                         'bob_id_xy21', 'cornell.edu', 'UNIT_TEST_AGENT')
        cevnt = CreateSubmission(creator=submitter, client=submitter)
        submission = cevnt.apply(None)

        nswfps = processor.WorkflowProcessor(workflow.SubmissionWorkflow,
                                             submission, seen)

        self.assertTrue(nswfps.can_proceed_to(nswfps.workflow[VerifyUser]))
        self.assertFalse(nswfps.can_proceed_to(nswfps.workflow[Authorship]))

        self.assertFalse(nswfps.can_proceed_to(nswfps.workflow[Policy]))

        self.assertFalse(nswfps.can_proceed_to(
            nswfps.workflow[Classification]))
        self.assertFalse(nswfps.can_proceed_to(nswfps.workflow[CrossList]))
        self.assertFalse(nswfps.can_proceed_to(nswfps.workflow[FileUpload]))
        self.assertFalse(nswfps.can_proceed_to(nswfps.workflow[Process]))
        self.assertFalse(nswfps.can_proceed_to(nswfps.workflow[Metadata]))
        self.assertFalse(nswfps.can_proceed_to(
            nswfps.workflow[OptionalMetadata]))
        self.assertFalse(nswfps.can_proceed_to(nswfps.workflow[FinalPreview]))
        self.assertFalse(nswfps.can_proceed_to(nswfps.workflow[Confirm]))

        self.assertEqual(nswfps.current_stage(), nswfps.workflow[VerifyUser])
