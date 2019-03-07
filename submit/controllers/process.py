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
import io
from werkzeug import MultiDict
from werkzeug.exceptions import InternalServerError, BadRequest, NotFound, \
    MethodNotAllowed

from flask import url_for, Markup
from wtforms import SelectField, widgets, HiddenField, validators
import bleach
import re
from arxiv import status
from arxiv.base import logging, alerts
from arxiv.forms import csrf
from arxiv.users.domain import Session
import arxiv.submission as events
from arxiv.submission.tasks import is_async
from arxiv.submission.services import compiler
from arxiv.submission.domain.submission import Compilation, SubmissionContent
from ..util import load_submission
from . import util

logger = logging.getLogger(__name__)

Response = Tuple[Dict[str, Any], int, Dict[str, Any]]  # pylint: disable=C0103


PLEASE_CONTACT_SUPPORT = Markup(
    'If you continue to experience problems, please contact'
    ' <a href="mailto:help@arxiv.org"> arXiv support</a>.'
)


def file_process(method: str, params: MultiDict, session: Session,
                 submission_id: int, token: str, **kwargs) -> Response:
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
    logger.debug("%s: %s, %s, %s, %s", method, params, session, submission_id,  token)
    if method == "GET":
        return compile_status(params, session, submission_id, token)
    elif method == "POST":
        if params.get('action') in ['previous', 'next', 'save_exit']:
            # User is not actually trying to process anything; let flow control
            # in the routes handle the response.
            return {}, status.HTTP_303_SEE_OTHER, {}
        return start_compilation(params, session, submission_id, token)
    else:
        return {}, status.HTTP_400_BAD_REQUEST, {}


def compile_status(params: MultiDict, session: Session, submission_id: int,
                   token: str, **kwargs) -> Response:
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
    # GET
    # submit.controllers.file_process.status

    compiler.set_auth_token(token)  # TODO: this is not stateless!
    submitter, client = util.user_and_client_from_session(session)
    submission, submission_events = load_submission(submission_id)
    form = CompilationForm()
    response_data = {
        'submission_id': submission_id,
        'submission': submission,
        'form': form,
        'compilations': submission.compilations
    }

    compilation = submission.latest_compilation
    is_current = compilation and \
        compilation.checksum == submission.source_content.checksum
    logger.debug('submission has processes %s', submission.processes)
    logger.debug('Submission has compilations %s', submission.compilations)
    logger.debug('Submission has latest compilation %s', compilation)
    response_data['must_process'] = (submission.source_content.source_format
                                     is not SubmissionContent.Format.PDF)
    if not compilation:    # if not Compilation, just show page
        return response_data, status.HTTP_200_OK, {}

    # if Compilation failure, then show errors, opportunity to restart
    if compilation.status is Compilation.Status.FAILED and is_current:
        response_data['status'] = "failed"
        response_data.update(_get_log(submission.source_content.identifier,
                                      submission.source_content.checksum))
    # if Compilation success, then show preview
    elif compilation.status is Compilation.Status.SUCCEEDED and is_current:
        response_data['status'] = "success"
        response_data.update(_get_log(submission.source_content.identifier,
                                      submission.source_content.checksum))
    elif compilation.status is Compilation.Status.IN_PROGRESS and is_current:
        response_data['status'] = "in_progress"
    else:  # if Compilation running, then show status, no restart
        response_data['status'] = None
    return response_data, status.HTTP_200_OK, {}


def start_compilation(params: MultiDict, session: Session, submission_id: int,
                      token: str, **kwargs) -> Response:
    compiler.set_auth_token(token)
    submitter, client = util.user_and_client_from_session(session)
    submission, submission_events = load_submission(submission_id)
    form = CompilationForm(params)
    response_data = {
        'submission_id': submission_id,
        'submission': submission,
        'form': form,
        'compilations': submission.compilations
    }

    if not form.validate():
        logger.debug("Invalid form data")
        return response_data, status.HTTP_400_BAD_REQUEST, {}
    try:
        logger.debug('Request compilation of source %s at checksum %s',
                     submission.source_content.identifier,
                     submission.source_content.checksum)
        compilation_status = compiler.compile(
            submission.source_content.identifier,
            submission.source_content.checksum
        )
        logger.debug("Requested compilation, %s", compilation_status)
        if compilation_status.status is compiler.Status.FAILED:
            alerts.flash_failure(f"Compilation failed")
    except compiler.BadRequest as e:
        logger.debug('Bad request to compiler for %s: %s', submission_id, e)
        alerts.flash_failure(
            f"We could not compile your submission. {PLEASE_CONTACT_SUPPORT}",
            title="Compilation failed"
        )
    except compiler.NoSuchResource as e:
        logger.debug('No such resource error for %s: %s', submission_id, e)
        alerts.flash_failure(
            f"We could not compile your submission. {PLEASE_CONTACT_SUPPORT}",
            title="Compilation failed"
        )

    failed = compilation_status.status is compiler.Status.FAILED
    in_progress = compilation_status.status is compiler.Status.IN_PROGRESS
    previous = [c.identifier for c in submission.compilations]
    new_compilation = compilation_status.identifier not in previous
    if in_progress or (failed and new_compilation):
        submission, stack = events.save(  # pylint: disable=W0612
            events.AddProcessStatus(
                creator=submitter,
                process=events.AddProcessStatus.Process.COMPILATION,
                service=compiler.NAME,
                version=compiler.VERSION,
                identifier=compilation_status.identifier
            ),
            submission_id=submission_id
        )
        alerts.flash_success(
            "We are compiling your submission. Please be patient.",
            title="Compilation started"
        )
    alerts.flash_hidden(compilation_status.to_dict(), 'compilation_status')
    redirect = url_for('ui.file_process', submission_id=submission_id)
    return response_data, status.HTTP_303_SEE_OTHER, {'Location': redirect}


def _get_log(identifier: str, checksum: str) -> dict:
    try:
        log = compiler.get_log(identifier, checksum)
        # Make linebreaks but escape everything else.
        log_output = log.stream.read().decode('utf-8')
    except compiler.NoSuchResource:
        log_output = "No log available."
    return {'log_output': log_output}


def file_preview(params, session: Session, submission_id: int, token: str,
                 **kwargs) -> Response:
    submitter, client = util.user_and_client_from_session(session)
    submission, submission_events = load_submission(submission_id)
    compiler.set_auth_token(token)
    prod = compiler.get_product(submission.source_content.identifier,
                                submission.source_content.checksum)
    headers = {'Content-Type': prod.content_type}
    return prod.stream, status.HTTP_200_OK, headers


def compilation_log(params, session: Session, submission_id: int, token: str,
                    **kwargs) -> Response:
    submitter, client = util.user_and_client_from_session(session)
    submission, submission_events = load_submission(submission_id)
    compiler.set_auth_token(token)
    checksum = params.get('checksum', submission.source_content.checksum)
    try:
        log = compiler.get_log(submission.source_content.identifier, checksum)
        headers = {'Content-Type': log.content_type}
        return log.stream, status.HTTP_200_OK, headers
    except compiler.NoSuchResource:
        raise NotFound("No log output produced")


def compile(params: MultiDict, session: Session, submission_id: int,
            token: str, **kwargs) -> Response:
    redirect = url_for('ui.file_process', submission_id=submission_id)
    return {}, status.HTTP_303_SEE_OTHER, {'Location': redirect}


class CompilationForm(csrf.CSRFForm):
    """Generate form to process compilation."""

    PDFLATEX = 'pdflatex'
    COMPILERS = [
        (PDFLATEX, 'PDFLaTeX')
    ]

    compiler = SelectField('Compiler', choices=COMPILERS,
                           default=PDFLATEX)
