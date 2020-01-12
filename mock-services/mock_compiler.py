"""Mock endpoint for compiler service."""

import os
from flask import Flask, jsonify
from typing import Callable, Union
from http import HTTPStatus as status
from flask import Blueprint, redirect, request, send_file
from flask import Response as FlaskResponse
from werkzeug.wrappers import Response as WkzResponse
from flask import Response as FlaskResponse
from flask import url_for

Response = Union[FlaskResponse, WkzResponse]


application = Flask(__name__)


# @application.route('/status', methods=['GET'])
# def get_status():
#     return 'ok'


base_url = '/<string:source_id>/<string:checksum>/<string:output_format>'

# Placeholder routines for retrieving various compiler generated files

def __get_autotex_log() -> str:
    log_file_path = '/opt/arxiv/data/autotex.log'
    return log_file_path

def __get_generated_pdf() -> str:
    pdf_file_path = '/opt/arxiv/data/mock.pdf'
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
    # response.headers.extend(headers.items())  # type: ignore
    #return response

    code = status.ACCEPTED
    """Redirect to the status endpoint."""
    location = url_for('get_status', source_id=source_id,
                       checksum=checksum, output_format=output_format)

    return {}, code, {'Location': location}


@application.route(base_url, methods=['GET'])
def get_status(source_id: str, checksum: str, output_format: str) -> Response:
    """Get the mock status of a compilation task."""
    #data = f'compilation status information: {source_id} : checksum: {checksum} fmt: {output_format}'
    data = {"checksum":f"{checksum}",
            "description":"Success!",
            "output_format":f"{output_format}",
            "owner":"1",
            "reason":None,
            "size_bytes":281064,
            "source_id":f"{source_id}",
            "status":"completed",
            "task_id":"1/XsMmoyHtfX8PgFLptd8AcA==/pdf"}
    response: Response = jsonify(data)
    response.status_code = status.OK
    # response.headers.extend(headers.items())    # type: ignore
    return response


@application.route(f'{base_url}/log', methods=['GET'])
def get_log(source_id: str, checksum: str, output_format: str) -> Response:
    """Get a mock compilation log."""
    """
    resp = controllers.get_log(source_id, checksum, output_format,
                               authorizer(scopes.READ_COMPILE))
    data, status_code, headers = resp
    response: Response = send_file(data['stream'],
                                   mimetype=data['content_type'],
                                   attachment_filename=data['filename'])
    """
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
    """
    data, code, head = controllers.get_product(source_id, checksum,
                                               output_format,
                                               authorizer(scopes.READ_COMPILE))
    response: Response = send_file(data['stream'],
                                   mimetype=data['content_type'],
                                   attachment_filename=data['filename'])
    response.set_etag(head.get('ETag'))
    """
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