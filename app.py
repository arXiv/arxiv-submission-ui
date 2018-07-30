"""Provides application for development purposes."""

from submit.factory import create_ui_web_app
from arxiv.submission.services import classic

app = create_ui_web_app()

with app.app_context():
    classic.create_all()
