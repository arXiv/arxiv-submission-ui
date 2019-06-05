"""Web Server Gateway Interface entry-point."""

from submit.factory import create_ui_web_app
import os
import logging

logging.getLogger('arxiv.submission.services.classic.interpolate') \
    .setLevel(logging.ERROR)
logging.getLogger('arxiv.base.alerts').setLevel(logging.ERROR)


__flask_app__ = create_ui_web_app()


def application(environ, start_response):
    """WSGI application factory."""
    global __flask_app__
    for key, value in environ.items():
        if key in __flask_app__.config and key != 'SERVER_NAME':
            __flask_app__.config[key] = value
            os.environ[key] = value
    return __flask_app__(environ, start_response)
