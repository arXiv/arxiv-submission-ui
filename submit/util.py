"""Utilities and helpers for the :mod:`submit` application."""

from typing import Optional, Tuple, List

from werkzeug.exceptions import NotFound

from arxiv.base.globals import get_application_global
import arxiv.submission as events


def load_submission(submission_id: Optional[int]) \
        -> Tuple[events.domain.Submission, List[events.domain.Event]]:
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
            submission, submission_events = events.load(submission_id)
        except events.exceptions.NoSuchSubmission as e:
            raise NotFound('No such submission.') from e
        if g is not None:
            setattr(g, f'submission_{submission_id}',
                    (submission, submission_events))
    if g is not None:
        return getattr(g, f'submission_{submission_id}')
    return submission, submission_events
