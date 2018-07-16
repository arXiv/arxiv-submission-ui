"""Tests for the submission application as a whole."""

from unittest import TestCase

from submit.factory import create_ui_web_app


class TestSubmissionWorkflow(TestCase):
    """Tests that progress through the submission workflow in various ways."""

    def setUp(self):
        """Create an application instance."""
        self.app = create_ui_web_app()
        
