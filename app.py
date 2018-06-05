"""Provides application for development purposes."""

from submit.factory import create_ui_web_app
from events.services import classic

app = create_ui_web_app()
app.config['CLASSIC_DATABASE_URI'] = 'sqlite://'

with app.app_context():
    classic.init_app(app)
    classic.create_all()
