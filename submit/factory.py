"""Application factory for references service components."""

import logging

from flask import Flask

from arxiv.base import Base
from arxiv.users import auth
from arxiv.base.middleware import wrap, request_logs
from arxiv.submission.services import classic

from submit.routes import ui
from . import filters


def create_ui_web_app() -> Flask:
    """Initialize an instance of the search frontend UI web application."""
    app = Flask('submit', static_folder='static', template_folder='templates')
    classic.init_app(app)
    app.config.from_pyfile('config.py')

    Base(app)
    auth.Auth(app)
    app.register_blueprint(ui.blueprint)

    wrap(app, [auth.middleware.AuthMiddleware])
    app.jinja_env.filters['group_files'] = filters.group_files
    app.jinja_env.filters['timesince'] = filters.timesince
    return app
