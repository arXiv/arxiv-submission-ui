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
    app.register_blueprint(ui.ui)

    wrap(app, [auth.middleware.AuthMiddleware])
    for filter_name, filter_func in filters.get_filters():
        app.jinja_env.filters[filter_name] = filter_func
    app.context_processor(ui.inject_get_next_stage_for_submission)
    return app
