"""This script runs the tests in :mod:`arxiv.base.app_tests`."""

import unittest

from arxiv.base.app_tests import *
from submit.factory import create_ui_web_app

app = create_ui_web_app()

if __name__ == '__main__':
    with app.app_context():
        unittest.main()