"""Mock file management app for testing and development."""

from datetime import datetime

from flask import Flask, Blueprint, jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge, BadRequest, \
    Unauthorized, Forbidden, NotFound

from arxiv import status

blueprint = Blueprint('filemanager', __name__)


@blueprint.route('/status')
def service_status():
    """Mock implementation of service status route."""
    return jsonify({'status': 'ok'})


@blueprint.route('/', methods=['POST'])
def upload_package():
    """Mock implementation of upload route."""
    if 'file' not in request.files:
        raise BadRequest('No file')
    if len(request.files['file'].read()) > 80:  # Arbitrary limit.
        raise RequestEntityTooLarge('Nope!')
    if 'Authorization' not in request.headers:
        raise Unauthorized('Nope!')
    if request.headers['Authorization'] != '!':     # Arbitrary value.
        raise Forbidden('No sir!')
    # Not sure what the response will look like yet.
    upload_status = dict(
        identifier=25,
        checksum='a1s2d3f4',
        size=593920,
        file_list=[dict(
            path='',
            name='thebestfile.pdf',
            file_type='PDF',
            added=datetime.now().isoformat(),
            size=20505,
            ancillary=False,
            errors=[]
        )],
        errors=[]
    )
    return jsonify(upload_status), status.HTTP_201_CREATED


@blueprint.route('/<upload_id>', methods=['POST'])
def add_file(upload_id):
    """Mock implementation of file upload route."""
    if int(upload_id) >= 25:
        raise NotFound('No such upload')
    if 'file' not in request.files:
        raise BadRequest('No file')
    if len(request.files['file'].read()) > 80:  # Arbitrary limit.
        raise RequestEntityTooLarge('Nope!')
    if 'Authorization' not in request.headers:
        raise Unauthorized('Nope!')
    if request.headers['Authorization'] != '!':     # Arbitrary value.
        raise Forbidden('No sir!')
    # Not sure what the response will look like yet.
    upload_status = dict(
        identifier=25,
        checksum='a1s2d3f4',
        size=593920,
        file_list=[dict(
            path='',
            name='thebestfile.pdf',
            file_type='PDF',
            added=datetime.now().isoformat(),
            size=20505,
            ancillary=False,
            errors=[]
        )],
        errors=[]
    )
    return jsonify(upload_status), status.HTTP_201_CREATED


def create_fm_app():
    """Generate a mock file management app."""
    app = Flask('filemanager')
    app.register_blueprint(blueprint)
    return app
