"""Utilities for routes."""

from typing import Optional, Callable
from functools import wraps

from flask import Response, request, redirect, url_for, session
from werkzeug.exceptions import BadRequest

from http import HTTPStatus as status
from arxiv.base import alerts, logging
from arxiv.base.globals import get_application_global
from ..domain.workflow import Stage, Workflow, SubmissionWorkflow, \
    ReplacementWorkflow
from ..domain import Submission
from ..util import load_submission

logger = logging.getLogger(__name__)

EXIT = 'ui.create_submission'


def get_workflow(submission: Submission) -> Workflow:
    if submission.version > 1:
        return ReplacementWorkflow(submission, session)
    return SubmissionWorkflow(submission, session)


def to_previous(workflow: Workflow, stage: Stage, ident: str) -> Response:
    previous_stage = workflow.previous_stage(stage)
    logger.debug('Redirecting to previous stage: %s', previous_stage)
    loc = url_for(f'ui.{previous_stage.endpoint}', submission_id=ident)
    return redirect(loc, code=status.SEE_OTHER)


def to_next(workflow: Workflow, stage: Stage, ident: str) -> Response:
    next_stage = workflow.next_stage(stage)
    logger.debug('Redirecting to next stage: %s', next_stage)
    loc = url_for(f'ui.{next_stage.endpoint}', submission_id=ident)
    return redirect(loc, code=status.SEE_OTHER)


def to_current(workflow: Workflow, stage: Stage, ident: str) -> Response:
    next_stage = workflow.current_stage
    alerts.flash_warning(f'Please {next_stage.label} before proceeding.')
    logger.debug('Redirecting to current stage: %s', next_stage)
    loc = url_for(f'ui.{next_stage.endpoint}', submission_id=ident)
    return redirect(loc, code=status.SEE_OTHER)


def flow_control(this_stage: Stage, exit: str = EXIT) -> Callable:
    """Get a decorator that handles redirection to next/previous steps."""
    PREVIOUS = 'previous'
    NEXT = 'next'
    SAVE_EXIT = 'save_exit'

    def deco(func: Callable) -> Callable:
        """Decorate func with workflow redirection."""
        @wraps(func)
        def wrapper(submission_id: str) -> Response:
            """Update the redirect to the next, previous, or exit page."""
            action = request.form.get('action')
            submission, _ = load_submission(submission_id)
            workflow = get_workflow(submission)

            try:
                if not workflow.can_proceed_to(this_stage):
                    return to_current(workflow, this_stage, submission_id)

            except ValueError:
                raise BadRequest('Request not allowed for this submission')

            # If the user has proceeded past an optional stage, consider it
            # to be completed.
            if not workflow.is_required(workflow.previous_stage(this_stage)) \
                    and workflow.previous_stage(this_stage) is not None:
                workflow.mark_complete(workflow.previous_stage(this_stage))

            # If the user selects "go back", we attempt to save their input
            # above. But if the input does not validate, we don't prevent them
            # from going to the previous step.
            try:
                response = func(submission_id)
            except BadRequest:
                if action == PREVIOUS:
                    return to_previous(workflow, this_stage, submission_id)
                raise

            # Intercept redirection and route based on workflow.
            if response.status_code == status.SEE_OTHER:
                workflow.mark_complete(this_stage)
                if action == NEXT:
                    return to_next(workflow, this_stage, submission_id)
                elif action == PREVIOUS:
                    return to_previous(workflow, this_stage, submission_id)
                elif action == SAVE_EXIT:
                    return redirect(url_for(exit),
                                    code=status.SEE_OTHER)
            return response    # No redirect; nothing to do.
        return wrapper
    return deco
