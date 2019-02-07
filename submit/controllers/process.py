"""
Controllers for process-related requests.

# Domain Changes
Submision.compilations

Compilation
task_id
source_etag
format
start_time
status

# Controller
- no history, is there a compilation that matches current source package

# GET
submit.controllers.file_process.status

if no Compilation, just show page
if Compilation running, then show status, no restart
if Compilation success, then show preview
if Compilation failure, then show errors, opportunity to restart

# POST
submit.controllers.file_process.compile
if Compilation matching etag, short-circuit
if no Compilation matching etag, create compilation

use CSRF form from arxiv.base to render the form, include a csrf_token.


plan of attack
-----------------
1. Update domain in submission.core
2. Add GET functionality in controllers
3. Add POST functionality in controller

  1  update submission core domain
  2a initial landing page
  3a create task
  2b get status of task
  2c show error
  2d show success
  3b short-circuit if task exists

2. Release updated domain in submission.core

"""

from typing import Tuple, Dict, Any, Optional

from werkzeug import MultiDict
from werkzeug.exceptions import InternalServerError, BadRequest,\
    MethodNotAllowed

from flask import url_for

from arxiv import status
from arxiv.base import logging, alerts
from arxiv.forms import csrf
from arxiv.users.domain import Session
from ..services import compiler

logger = logging.getLogger(__name__)

Response = Tuple[Dict[str, Any], int, Dict[str, Any]]  # pylint: disable=C0103

def file_process(method: str, session: Session, submission_id: int, token: str) -> Response:
    """
    Process the file compilation project.

    Parameters
    ----------
    method : str
        ``GET`` or ``POST``
    session : :class:`Session`
        The authenticated session for the request.
    submission_id : int
        The identifier of the submission for which the upload is being made.
    token : str
        The original (encrypted) auth token on the request. Used to perform
        subrequests to the file management service.

    Returns
    -------
    dict
        Response data, to render in template.
    int
        HTTP status code. This should be ``200`` or ``303``, unless something
        goes wrong.
    dict
        Extra headers to add/update on the response. This should include
        the `Location` header for use in the 303 redirect response, if
        applicable.
    """
    if method == "GET":
        return compile_status(session, submission_id, token)
    #elif method == "POST":
    #    return compile(seesion, submission_id, token)
    else:
        return {}, status.HTTP_400_BAD_REQUEST, {}

def compile_status(session: Session, submission_id: int, token: str) -> Response:
    """
    Returns the status of a compilation.

    Parameters
    ----------
    session : :class:`Session`
        The authenticated session for the request.
    submission_id : int
        The identifier of the submission for which the upload is being made.
    token : str
        The original (encrypted) auth token on the request. Used to perform
        subrequests to the file management service.

    Returns
    -------
    dict
        Response data, to render in template.
    int
        HTTP status code. This should be ``200`` or ``303``, unless something
        goes wrong.
    dict
        Extra headers to add/update on the response. This should include
        the `Location` header for use in the 303 redirect response, if
        applicable.
    """
    compiler.set_auth_token(token)
    try:
        compiler.request_compilation(submission_id)
    except compiler.BadRequest as e:
        logger.debug(f'Bad request to compiler for {submission_id}')
        return {'status': 'failed', 'warnings' : ['This is only a test.']}, status.HTTP_400_BAD_REQUEST, {}

    redirect = url_for('ui.file_process', submission_id=submission_id)
    return {}, status.HTTP_303_SEE_OTHER, {'Location': redirect}

def compile(session: Session, submission_id: int, token: str) -> Response:
    redirect = url_for('ui.file_process', submission_id=submission_id)
    return {}, status.HTTP_303_SEE_OTHER, {'Location': redirect}