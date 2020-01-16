"""Handles which UI route to proceeded in submission workflows."""


from http import HTTPStatus as status
from functools import wraps
from typing import Optional, Callable, Union

from flask import request, redirect, url_for, session
from flask import Response as FResponse
from werkzeug import Response as WResponse
from werkzeug.exceptions import BadRequest

from arxiv.base import alerts, logging
from arxiv.submission.domain import Submission

# from .workflow import Stage, Workflow, SubmissionWorkflow, \
#     ReplacementWorkflow, BaseStage
from submit.workflow import SubmissionWorkflow, ReplacementWorkflow
from submit.workflow.stages import Stage
from submit.workflow.processor import WorkflowProcessor

from submit.util import load_submission


logger = logging.getLogger(__name__)

EXIT = 'ui.create_submission'
PREVIOUS = 'previous'
NEXT = 'next'
SAVE_EXIT = 'save_exit'

Response = Union[FResponse, WResponse]


def endpoint_name() -> Optional[str]:
    """Get workflow compatable endpoint name from request"""
    if request.url_rule is None:
        return None
    endpoint = request.url_rule.endpoint
    if '.' in endpoint:
        _, endpoint = endpoint.split('.', 1)
    return endpoint


def get_seen():
    """Get seen steps from user session."""
    # TODO Fix seen to handle mutlipe submissions at the same time
    return session.get('steps_seen', {})


def put_seen(seen):
    """Put the seen steps into the users session."""
    # TODO Fix seen to handle mutlipe submissions at the same time
    session['steps_seen'] = seen


def get_workflow(submission: Optional[Submission]) -> WorkflowProcessor:
    """Guesses the workflow based on the submission and its version."""
    if submission is not None and submission.version > 1:
        return WorkflowProcessor(ReplacementWorkflow, submission, get_seen())
    return WorkflowProcessor(SubmissionWorkflow, submission, get_seen())


def to_stage(stage: Optional[Stage], ident: str) -> Response:
    """Return a flask redirect to Stage."""
    if stage is None:
        return redirect(url_for('ui.create_submission'), code=status.SEE_OTHER)
    loc = url_for(f'ui.{stage.endpoint}', submission_id=ident)
    return redirect(loc, code=status.SEE_OTHER)



def to_previous(wfs: WorkflowProcessor, stage: Stage, ident: str) -> Response:
    """Return a flask redirect to the previous stage."""
    return to_stage(wfs.previous_stage(stage), ident)



def to_next(wfs: WorkflowProcessor, stage: Stage, ident: str) -> Response:
    """Return a flask redirect to the next stage."""
    return to_stage(wfs.next_stage(stage), ident)


def to_current(wfs: WorkflowProcessor, ident: str, flash: bool = True) -> Response:
    """Return a flask redirect to the stage required by the workflow."""
    next_stage = wfs.current_stage()
    if flash:
        alerts.flash_warning(f'Please {next_stage.label} before proceeding.')
    return to_stage(next_stage, ident)



def flow_control(blueprint_this_stage: Optional[Stage] = None, exit: str = EXIT) -> Callable:
    """Get a decorator that wraps a controller to handle redirection to
    next/previous steps.

    Parameters
    ----------

    blueprint_this_stage :
    Usually, this will be None and the stage will be determined from the
    context by checking the submission and route. If passed, this will
    be used as the stage for controlling the flow of the wrapped
    controller. This will allow a auxilrary route to be used with a stage,
    ex delete_all_files route for the stage FileUpload.

    exit:
    Route to redirect to when user selectes exit action.
    """
    def deco(func: Callable) -> Callable:
        """Decorate func with workflow redirection."""
        @wraps(func)
        def wrapper(submission_id: str) -> Response:
            """Update the redirect to the next, previous, or exit page."""
            action = request.form.get('action')
            submission, _ = load_submission(submission_id)
            workflow = request.workflow
            this_stage = blueprint_this_stage or workflow.workflow[endpoint_name()]

            if workflow.is_complete() and \
               not this_stage == workflow.confirmation:
                return to_stage(workflow.confirmation, submission_id)
            
            if not workflow.can_proceed_to(this_stage):
                return to_current(workflow, submission_id)

            # Mark the previous state as seen.
            # if workflow.previous_stage(this_stage):
            #    workflow.mark_seen(workflow.previous_stage(this_stage))

            # NOTE: The below conditional is subsubmed by the above conditional

# If the user has proceeded past an optional stage, consider it
# to be seen.
# if not workflow.is_required(workflow.previous_stage(this_stage)) \
#         and workflow.previous_stage(this_stage) is not None:
#     workflow.mark_seen(workflow.previous_stage(this_stage))

            # If the user selects "go back", we attempt to save their input
            # above. But if the input does not validate, we don't prevent them
            # from going to the previous step.
            try:
                response = func(submission_id)
                if response.status_code == status.BAD_REQUEST:
                    raise BadRequest
            except BadRequest:
                if action == PREVIOUS:
                    return to_previous(workflow, this_stage, submission_id)
                raise

            workflow.mark_seen(this_stage)
            put_seen(workflow.seen)
            # Intercept redirection and route based on workflow.
            if response.status_code == status.SEE_OTHER:
                # workflow.mark_seen(this_stage)
                if action == PREVIOUS:
                    return to_previous(workflow, this_stage, submission_id)
                if action == SAVE_EXIT:
                    return redirect(url_for(exit), code=status.SEE_OTHER)
                else: # default To next stage
                    return to_next(workflow, this_stage, submission_id)
            return response    # No redirect; nothing to do.
        return wrapper
    return deco
