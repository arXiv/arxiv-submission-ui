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
from http import HTTPStatus as status
from arxiv.base import logging, alerts
from arxiv.forms import csrf
from arxiv.users.domain import Session
from arxiv.integration.api import exceptions
from arxiv.submission import save, SaveError, AddProcessStatus, Submission
from arxiv.submission.tasks import is_async, get_task_status
from arxiv.submission.services.compiler import Compiler
from arxiv.submission.domain.compilation import Status
from arxiv.submission.domain.submission import Compilation, SubmissionContent
from ..util import load_submission
from .util import validate_command, user_and_client_from_session

logger = logging.getLogger(__name__)

Response = Tuple[Dict[str, Any], int, Dict[str, Any]]  # pylint: disable=C0103


SUPPORT = Markup(
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
    logger.debug("%s: %s, %s, %s, %s", method, params, session, submission_id,
                 token)
    if method == "GET":
        return compile_status(params, session, submission_id, token)
    elif method == "POST":
        if params.get('action') in ['previous', 'next', 'save_exit']:
            # User is not actually trying to process anything; let flow control
            # in the routes handle the response.
            return {}, status.SEE_OTHER, {}
        return start_compilation(params, session, submission_id, token)
    raise MethodNotAllowed('Unsupported request')


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

    submitter, client = user_and_client_from_session(session)
    submission, submission_events = load_submission(submission_id)
    form = CompilationForm()
    response_data = {
        'submission_id': submission_id,
        'submission': submission,
        'form': form,
        'compilations': submission.compilations,
        'status': None,
        'must_process': _must_process(submission)
    }

    compilation = submission.latest_compilation
    if not compilation:     # Nothing to do.
        return response_data, status.OK, {}

    # Determine whether the current state of the uploaded source content has
    # been compiled.
    is_current = compilation.checksum == submission.source_content.checksum
    if is_current:
        response_data['status'] = compilation.status
        response_data['current_compilation'] = compilation

    # if Compilation failure, then show errors, opportunity to restart.
    # if Compilation success, then show preview.
    terminal_states = [Compilation.Status.FAILED, Compilation.Status.SUCCEEDED]
    if is_current and compilation.status in terminal_states:
        response_data.update(_get_log(submission.source_content.identifier,
                                      submission.source_content.checksum,
                                      token))

    # TODO: make sure that monitoring task is still running; if not, check and
    # update the status directly.
    # elif is_current and compilation.status == Compilation.Status.IN_PROGRESS:
    #   ...
    # print(get_task_status(submission.processes[-1].monitoring_task))
    return response_data, status.OK, {}


def start_compilation(params: MultiDict, session: Session, submission_id: int,
                      token: str, **kwargs) -> Response:
    submitter, client = user_and_client_from_session(session)
    submission, submission_events = load_submission(submission_id)
    form = CompilationForm(params)
    response_data = {
        'submission_id': submission_id,
        'submission': submission,
        'form': form,
        'compilations': submission.compilations,
        'status': None,
        'must_process': _must_process(submission)
    }

    if not form.validate():
        raise BadRequest(response_data)
    try:
        stat = Compiler.compile(submission.source_content.identifier,
                                submission.source_content.checksum, token)
    except exceptions.RequestFailed as e:
        alerts.flash_failure(f"We couldn't compile your submission. {SUPPORT}",
                             title="Compilation failed")
        raise InternalServerError(response_data) from e

    response_data['status'] = stat
    if stat.status is Status.FAILED:
        alerts.flash_failure(f"Compilation failed")

    failed = stat.status is Status.FAILED
    succeeded = stat.status is Status.SUCCEEDED
    in_progress = stat.status is Status.IN_PROGRESS
    previous = [c.identifier for c in submission.compilations]
    new_compilation = stat.identifier not in previous
    process = AddProcessStatus.Process.COMPILATION
    if in_progress or (new_compilation and (failed or succeeded)):
        command = AddProcessStatus(creator=submitter, client=client,
                                   process=process, service=Compiler.NAME,
                                   version=Compiler.VERSION,
                                   identifier=stat.identifier)
        if not validate_command(form, command, submission):
            raise BadRequest(response_data)

        try:
            submission, _ = save(command, submission_id=submission_id)
        except SaveError as e:
            raise InternalServerError(response_data) from e
        response_data['submission'] = submission
        alerts.flash_success(
            "We are compiling your submission. This may take a minute or two."
            " This page will refresh automatically every 5 seconds. You can "
            " also refresh this page manually to check the current status. ",
            title="Compilation started"
        )
    alerts.flash_hidden(stat.to_dict(), 'compilation_status')
    redirect = url_for('ui.file_process', submission_id=submission_id)
    return response_data, status.SEE_OTHER, {'Location': redirect}


def _get_log(identifier: str, checksum: str, token: str) -> dict:
    try:
        log = Compiler.get_log(identifier, checksum, token)
        # Make linebreaks but escape everything else.
        log_output = log.stream.read().decode('utf-8')
    except exceptions.NotFound:
        log_output = "No log available."
    return {'log_output': log_output}


def file_preview(params, session: Session, submission_id: int, token: str,
                 **kwargs) -> Response:
    submitter, client = user_and_client_from_session(session)
    submission, submission_events = load_submission(submission_id)
    prod = Compiler.get_product(submission.source_content.identifier,
                                submission.source_content.checksum, token)
    headers = {'Content-Type': prod.content_type}
    return prod.stream, status.OK, headers


def compilation_log(params, session: Session, submission_id: int, token: str,
                    **kwargs) -> Response:
    submitter, client = user_and_client_from_session(session)
    submission, submission_events = load_submission(submission_id)
    checksum = params.get('checksum', submission.source_content.checksum)
    try:
        log = Compiler.get_log(submission.source_content.identifier, checksum,
                               token)
        headers = {'Content-Type': log.content_type}
        return log.stream, status.OK, headers
    except exceptions.NotFound:
        raise NotFound("No log output produced")


def compile(params: MultiDict, session: Session, submission_id: int,
            token: str, **kwargs) -> Response:
    redirect = url_for('ui.file_process', submission_id=submission_id)
    return {}, status.SEE_OTHER, {'Location': redirect}


class CompilationForm(csrf.CSRFForm):
    """Generate form to process compilation."""

    PDFLATEX = 'pdflatex'
    COMPILERS = [
        (PDFLATEX, 'PDFLaTeX')
    ]

    compiler = SelectField('Compiler', choices=COMPILERS,
                           default=PDFLATEX)


def _must_process(submission: Submission) -> bool:
    return submission.source_content.source_format \
        is not SubmissionContent.Format.PDF
