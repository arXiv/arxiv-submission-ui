"""Web Server Gateway Interface entry-point."""

from submit.factory import create_ui_web_app
import os
import logging

logging.getLogger('arxiv.submission.services.classic.interpolate') \
    .setLevel(logging.ERROR)
logging.getLogger('arxiv.base.alerts').setLevel(logging.ERROR)


_application = create_ui_web_app()


def application(environ, start_response):
    """WSGI application factory."""
    for key, value in environ.items():
        if key == 'SERVER_NAME':
            continue
        if key in _application.config:
            _application.config[key] = value
    print(_application.config)
    return _application(environ, start_response)
