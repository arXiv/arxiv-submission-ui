"""Provides application for development purposes."""

from submit.factory import create_ui_web_app
from arxiv.submission.services import classic
import logging

logging.getLogger('arxiv.submission.services.classic.interpolate') \
    .setLevel(logging.DEBUG)
logging.getLogger('arxiv.submission.services.classic.models') \
    .setLevel(logging.DEBUG)
logging.getLogger('arxiv.base.alerts').setLevel(logging.ERROR)

app = create_ui_web_app()

with app.app_context():
    try:
        classic.create_all()
    except Exception:
        pass
