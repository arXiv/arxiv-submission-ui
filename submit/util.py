"""Utilities and helpers for the :mod:`submit` application."""

from typing import Callable, Any, Dict, Tuple, Optional, List
from functools import wraps

from flask import url_for, request, redirect
from werkzeug.exceptions import InternalServerError, NotFound, BadRequest
from werkzeug import MultiDict

from arxiv.base.globals import get_application_global
from arxiv import status
from arxiv.base import alerts, logging
import arxiv.submission as events
from arxiv.users.domain import Session

from .domain import SubmissionStage

PREVIOUS = 'previous'
NEXT = 'next'
SAVE_EXIT = 'save_exit'

Response = Tuple[Dict[str, Any], int, Dict[str, Any]]  # pylint: disable=C0103

logger = logging.getLogger(__name__)


def load_submission(submission_id: Optional[int]) -> events.domain.Submission:
    """
    Load a submission by ID.

    Parameters
    ----------
    submission_id : int

    Returns
    -------
    :class:`events.domain.Submission`

    Raises
    ------
    :class:`werkzeug.exceptions.NotFound`
        Raised when there is no submission with the specified ID.

    """
    if submission_id is None:
        raise NotFound('No such submission.')

    g = get_application_global()
    if g is None or f'submission_{submission_id}' not in g:
        try:
            submission, _ = events.load(submission_id)
        except events.exceptions.NoSuchSubmission as e:
            raise NotFound('No such submission.') from e
        if g is not None:
            setattr(g, f'submission_{submission_id}', submission)
    if g is not None:
        return getattr(g, f'submission_{submission_id}')
    return submission


def flow_control(this_stage: str, exit_page: str = 'user') -> Callable:
    """Get a decorator that handles redirection to next/previous steps."""
    def deco(func: Callable) -> Callable:
        """Decorator that applies next/previous redirection."""
        @wraps(func)
        def wrapper(submission_id: str) -> Response:
            """Update the redirect to the next, previous, or exit page."""
            action = request.form.get('action')
            logger.debug('Handling request to %s with action %s',
                         this_stage, action)
            submission_stage = SubmissionStage(load_submission(submission_id))
            logger.debug('Current stage is %s', submission_stage.current_stage)

            if submission_stage.before(this_stage):
                alerts.flash_warning(
                    'Please complete this stage before proceeding.'
                )
                return redirect(url_for(
                    f'ui.{submission_stage.current_stage}',
                    submission_id=submission_id
                ))

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
                                            submission_id=submission_id))
                raise
            if response.status_code == status.HTTP_400_BAD_REQUEST \
                    and action == PREVIOUS:
                target = submission_stage.get_previous_stage(this_stage)
                logger.debug('Redirecting to previous stage: %s', target)
                return redirect(url_for(f'ui.{target}',
                                submission_id=submission_id))

            # No redirect; nothing to do.
            if response.status_code != status.HTTP_303_SEE_OTHER:
                return response

            if action == NEXT:
                response = redirect(url_for(
                    f'ui.{submission_stage.get_next_stage(this_stage)}',
                    submission_id=submission_id
                ))
            elif action == PREVIOUS:
                target = submission_stage.get_previous_stage(this_stage)
                logger.debug('Redirecting to previous stage: %s', target)
                response = redirect(url_for(f'ui.{target}',
                                            submission_id=submission_id))
            elif action == SAVE_EXIT:
                response = redirect(url_for(exit_page))
            return response
        return wrapper
    return deco
