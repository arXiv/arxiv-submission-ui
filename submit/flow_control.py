"""Utilities for routes."""

from typing import Optional, Callable
from functools import wraps

from flask import Response, request, redirect, url_for, session
from werkzeug.exceptions import BadRequest

from http import HTTPStatus as status
from arxiv.base import alerts, logging
from arxiv.base.globals import get_application_global
from .domain.workflow import Stage, Workflow, SubmissionWorkflow, \
    ReplacementWorkflow
from .domain import Submission
from .util import load_submission

logger = logging.getLogger(__name__)

EXIT = 'ui.create_submission'


def get_workflow(submission: Optional[Submission]) -> Workflow:
    if submission is not None and submission.version > 1:
        return ReplacementWorkflow(submission, session)
    return SubmissionWorkflow(submission, session)


def to_stage(workflow: Workflow, stage: Stage, ident: str) -> Response:
    if stage is None:
        return redirect(url_for('ui.create_submission'), code=status.SEE_OTHER)
    loc = url_for(f'ui.{stage.endpoint}', submission_id=ident)
    return redirect(loc, code=status.SEE_OTHER)


def to_previous(workflow: Workflow, stage: Stage, ident: str) -> Response:
    return to_stage(workflow, workflow.previous_stage(stage), ident)


def to_next(workflow: Workflow, stage: Stage, ident: str) -> Response:
    return to_stage(workflow, workflow.next_stage(stage), ident)


def to_current(workflow: Workflow, stage: Stage, ident: str,
               flash: bool = True) -> Response:
    next_stage = workflow.current_stage
    if flash:
        alerts.flash_warning(f'Please {next_stage.label} before proceeding.')
    return to_stage(workflow, next_stage, ident)


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

            if workflow.complete and not this_stage == workflow.confirmation:
                return to_stage(workflow, workflow.confirmation, submission_id)

            try:
                if not workflow.can_proceed_to(this_stage):
                    return to_current(workflow, this_stage, submission_id)

            except ValueError:
                raise BadRequest('Request not allowed for this submission')

            # Mark the previous state as complete.
            if workflow.previous_stage(this_stage):
                workflow.mark_complete(workflow.previous_stage(this_stage))

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
            if action == PREVIOUS and \
                    response.status_code == status.BAD_REQUEST:
                return to_previous(workflow, this_stage, submission_id)

            # Intercept redirection and route based on workflow.
            if response.status_code == status.SEE_OTHER:
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
