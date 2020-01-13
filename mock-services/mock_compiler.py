"""Mock endpoint for compiler service."""

import os
import logging
from http import HTTPStatus as status
from typing import Callable, Union
from werkzeug.wrappers import Response as WkzResponse
from flask import Flask, jsonify
#from flask import Response as FlaskResponse
from flask import Blueprint, redirect, request, send_file
from flask import Response as FlaskResponse
from flask import url_for

Response = Union[FlaskResponse, WkzResponse]

logger = logging.getLogger(__name__)

application = Flask(__name__)


# Fake compilation status changes [completed, in_progress, failed]
#
# The submission UI process page gets a little confused when the compilation
# status is already 'completed' when you advance to the process page.
#
# The status needs to start as None or Not Found when we hit process page.
#
# Once we initiate compilation we will return 'in_process' the first
# time get_status. This gives you the 'Processing Underway' process page view.
#
# Subsequent requests, like after the UI waits five seconds, will return
# the 'completed' status. This results in the "Processing Successful" view.
#
# We won't worry about the 'failed' state for now.
#
# Dictionary key will be source_id and value will be status value.

status_directory = '/opt/arxiv/data/'

def compilation_request_file_path(source_id: str) -> str:
    """Get the path to compilation request state file."""
    return f"{status_directory}{source_id}_compile_request"

def in_compilation_request(source_id: str) -> bool:
    """Flag active compilation state."""
    return bool(os.path.exists(compilation_request_file_path(source_id)))

def completed_status_file_path(source_id: str) -> str:
    """Get the path to completed state file."""
    return f"{status_directory}{source_id}_completed"

def in_progress_status_file_path(source_id: str) -> str:
    """Get the path to in_progress state file."""
    return f"{status_directory}{source_id}_in_progress"

def get_compilation_status(source_id: str) -> str:
    """Get compilation status."""
    if in_compilation_request(source_id) \
            and os.path.exists(completed_status_file_path(source_id)):
        clear_compilation_status(source_id)
        return 'completed'

    if in_compilation_request(source_id) \
            and os.path.exists(in_progress_status_file_path(source_id)):
        set_completed_compilation_status(source_id)
        return 'in_progress'

    if in_compilation_request(source_id):
        set_in_progress_compilation_status(source_id)
        return 'in_progress'

    return None

def set_in_compilation(source_id: str) -> str:
    """Set that we are in compilation mode."""
    # Make note that we've already answered a status request
    open(compilation_request_file_path(source_id), 'a').close()

def set_in_progress_compilation_status(source_id: str) -> str:
    """Note fake compilation requested."""
    # Make note that we've already answered a status request
    open(in_progress_status_file_path(source_id), 'a').close()

def set_completed_compilation_status(source_id: str) -> str:
    """Set compilation status to 'completed'."""
    # Make note that we've already answered a status request
    open(completed_status_file_path(source_id), 'a').close()

def clear_compilation_status(source_id: str) -> str:
    """Clear out the status every time a compile request is made."""
    if os.path.exists(in_progress_status_file_path(source_id)):
        os.remove(in_progress_status_file_path(source_id))

    if os.path.exists(completed_status_file_path(source_id)):
        os.remove(completed_status_file_path(source_id))

    if os.path.exists(compilation_request_file_path(source_id)):
        os.remove(compilation_request_file_path(source_id))


base_url = '/<string:source_id>/<string:checksum>/<string:output_format>'

# Placeholder routines for retrieving various compiler generated files

def __get_autotex_log() -> str:
    # .log files are ignored in .gitignore thus not naming log 'autotex.log'
    log_file_path = '/opt/arxiv/data/compilation_log'
    return log_file_path

def __get_generated_pdf() -> str:
    pdf_file_path = '/opt/arxiv/data/preview.pdf'
    return pdf_file_path


@application.route('/status', methods=['GET'])
def get_service_status() -> Union[str, Response]:
    """Return mock compiler service status code."""
    # data, code, headers = controllers.service_status()
    data = {}
    data['store'] = True
    data['compiler'] = True
    data['filemanager'] = True
    response: Response = jsonify(data)
    response.status_code = status.OK
    # response.headers.extend(headers.items())  # type: ignore
    return response


@application.route('/', methods=['POST'])
def compile() -> Response:
    """Mock compile route."""
    request_data = request.get_json(force=True)

    # We are not going to validate these values
    source_id = str(request_data.get('source_id', ''))
    checksum = str(request_data.get('checksum', ''))
    output_format = request_data.get('output_format', 'pdf')
    data = 'initiating compilation'
    response: Response = jsonify(data)
    response.status_code = status.OK

    # Set the fake status
    set_in_compilation(source_id)

    code = status.ACCEPTED

    #Redirect to the status endpoint.
    location = url_for('get_status', source_id=source_id,
                       checksum=checksum, output_format=output_format)

    return {}, code, {'Location': location}


@application.route(base_url, methods=['GET'])
def get_status(source_id: str, checksum: str, output_format: str) -> Response:
    """Get the mock status of a compilation task."""
    # Only call this once as state may change each time you check status
    compilation_status = get_compilation_status(source_id)

    # if compilation_status(source_id) == None:
    if compilation_status is None:
        data = {"reason": "No such compilation task"}
        response: Response = jsonify(data)
        response.status_code = status.NOT_FOUND
    else:
        data = {"checksum": f"{checksum}",
                "description": "Success!",
                "output_format": f"{output_format}",
                "owner": "1",
                "reason": None,
                "size_bytes": 281064,
                "source_id": f"{source_id}",
                "status": compilation_status,
                "task_id": "1/XsMmoyHtfX8PgFLptd8AcA==/pdf"
                }
        response: Response = jsonify(data)
        response.status_code = status.OK

    # response.headers.extend(headers.items())    # type: ignore
    return response


@application.route(f'{base_url}/log', methods=['GET'])
def get_log(source_id: str, checksum: str, output_format: str) -> Response:
    """Get a mock compilation log."""
    logger.info("get log: %s/%s/%s", source_id, checksum, output_format)

    log_file_path = __get_autotex_log()
    log_file_name = os.path.basename(log_file_path)

    f = open(log_file_path, "rb")
    data = {
        'stream': f,
        'content_type': 'text/plain',
        'filename': f'{log_file_name}'
    }

    code = status.OK
    response: Response = send_file(data['stream'],
                                   mimetype=data['content_type'],
                                   attachment_filename=data['filename'])
    response.status_code = code
    return response


@application.route(f'{base_url}/product', methods=['GET'])
def get_product(source_id: str, checksum: str, output_format: str) -> Response:
    """Get a mock compilation product."""
    logger.info("get product: %s/%s/%s", source_id, checksum, output_format)

    pdf_file_path = __get_generated_pdf()
    pdf_file_name = os.path.basename(pdf_file_path)

    f = open(pdf_file_path, "rb")
    data = {
        'stream': f,
        'content_type': 'application/pdf',
        'filename': f'{pdf_file_name}'
    }
    code = status.OK
    response: Response = send_file(data['stream'],
                                   mimetype=data['content_type'],
                                   attachment_filename=data['filename'])

    response.status_code = code
    return response
