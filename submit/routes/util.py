"""Utilities for routes."""

from typing import Optional, Callable
from functools import wraps

from flask import Response, request, redirect, url_for
from werkzeug.exceptions import BadRequest

from arxiv import status
from arxiv.base import alerts, logging
from arxiv.base.globals import get_application_global
from ..domain import SubmissionStage
from ..util import load_submission

logger = logging.getLogger(__name__)


def flow_control(this_stage: str, exit_page: str = 'user') -> Callable:
    """Get a decorator that handles redirection to next/previous steps."""
    PREVIOUS = 'previous'
    NEXT = 'next'
    SAVE_EXIT = 'save_exit'

    def deco(func: Callable) -> Callable:
        """Decorator that applies next/previous redirection."""
        @wraps(func)
        def wrapper(submission_id: str) -> Response:
            """Update the redirect to the next, previous, or exit page."""
            action = request.form.get('action')
            submission_stage = SubmissionStage(load_submission(submission_id))
            # Set the stage handled by this endpoint.
            g = get_application_global()
            if g:
                g.this_stage = this_stage
                g.submission_stage = submission_stage

            if not submission_stage.can_proceed_to(this_stage):
                next_stage = submission_stage.next_required_stage
                label = submission_stage.LABELS[next_stage]
                alerts.flash_warning(
                    f'Please {label} before proceeding.'
                )
                return redirect(url_for(
                    f'ui.{next_stage}',
                    submission_id=submission_id
                ), code=status.HTTP_303_SEE_OTHER)

            # If the user selects "go back", we attempt to save their input
            # above. But if the input does not validate, we don't prevent them
            # from going to the previous step.
            try:
                response = func(submission_id)
            except BadRequest:
                logger.debug('Caught a BadRequest')
                if action == PREVIOUS:
                    target = submission_stage.get_previous_stage(this_stage)
                    logger.debug('Redirecting to previous stage: %s', target)
                    return redirect(url_for(f'ui.{target}',
                                            submission_id=submission_id),
                                    code=status.HTTP_303_SEE_OTHER)
                raise
            if response.status_code == status.HTTP_400_BAD_REQUEST \
                    and action == PREVIOUS:
                target = submission_stage.get_previous_stage(this_stage)
                logger.debug('Redirecting to previous stage: %s', target)
                return redirect(url_for(f'ui.{target}',
                                        submission_id=submission_id),
                                code=status.HTTP_303_SEE_OTHER)

            # No redirect; nothing to do.
            if response.status_code != status.HTTP_303_SEE_OTHER:
                return response

            if action == NEXT:
                response = redirect(url_for(
                    f'ui.{submission_stage.get_next_stage(this_stage)}',
                    submission_id=submission_id
                ), code=status.HTTP_303_SEE_OTHER)
            elif action == PREVIOUS:
                target = submission_stage.get_previous_stage(this_stage)
                logger.debug('Redirecting to previous stage: %s', target)
                response = redirect(url_for(f'ui.{target}',
                                            submission_id=submission_id),
                                    code=status.HTTP_303_SEE_OTHER)
            elif action == SAVE_EXIT:
                response = redirect(url_for(exit_page),
                                    code=status.HTTP_303_SEE_OTHER)
            return response
        return wrapper
    return deco


def inject_stage() -> dict:
    """
    Injects the submissions stage and endpoint stage into the template.
    """
    ctx = {}
    g = get_application_global()
    if g:
        if 'submission_stage' in g:
            ctx['stage'] = g.submission_stage
        if 'this_stage' in g:
            ctx['this_stage'] = g.this_stage
    return ctx
