"""Application factory for references service components."""

import logging

from flask import Flask

from arxiv.base import Base
from arxiv.users import auth
from arxiv.base.middleware import wrap, request_logs
from arxiv.submission.services import classic
from arxiv.submission import init_app

from .routes import ui
from .services import FileManager
from . import filters
import logging

logging.getLogger('arxiv.submission.services.classic.interpolate').setLevel(40)
logging.getLogger('arxiv.submission.domain.event.event').setLevel(40)


def create_ui_web_app() -> Flask:
    """Initialize an instance of the search frontend UI web application."""
    app = Flask('submit', static_folder='static', template_folder='templates')
    classic.init_app(app)
    init_app(app)
    FileManager.init_app(app)
    app.config.from_pyfile('config.py')

    Base(app)
    auth.Auth(app)
    app.register_blueprint(ui.ui)

    wrap(app, [auth.middleware.AuthMiddleware])
    for filter_name, filter_func in filters.get_filters():
        app.jinja_env.filters[filter_name] = filter_func
    return app
