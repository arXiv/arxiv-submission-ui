"""Tests for workflow"""

from unittest import TestCase, mock
from submit import workflow
from submit.workflow import processor


class TestNewSubmissionWorkflow(TestCase):

    def testVerifyUser(self):
        seen = {}
        submission = mock.MagicMock(submission_id=1234,
                                    is_finalized=False,
                                    submitter_contact_verified=False)        
        nswfps = processor.WorkflowProcessor(
            workflow.SubmissionWorkflow,
            submission,
            seen)
        self.assertTrue(nswfps.can_proceed_to(nswfps.workflow.order[0]))
        self.assertFalse(nswfps.can_proceed_to(nswfps.workflow.order[1]))
        self.assertEqual(nswfps.current_stage(), nswfps.workflow.order[0])
        
        
        
        
    
