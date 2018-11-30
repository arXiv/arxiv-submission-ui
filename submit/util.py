"""Utilities and helpers for the :mod:`submit` application."""

from typing import Optional, Tuple, List
from datetime import datetime
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


# TODO: remove me!
def publish_submission(submission_id: int) -> None:
    """WARNING WARNING WARNING this is for testing purposes only."""
    dbss = events.services.classic._get_db_submission_rows(submission_id)
    i = events.services.classic._get_head_idx(dbss)
    head = dbss[i]
    session = events.services.classic.current_session()
    if head.is_published():
        return
    head.status = events.services.classic.models.Submission.PUBLISHED
    if head.document is None:
        paper_id = datetime.now().strftime('%s')[-4:] \
            + "." \
            + datetime.now().strftime('%s')[-5:]
        head.document = \
            events.services.classic.models.Document(paper_id=paper_id)
        head.doc_paper_id = paper_id
    session.add(head)
    session.commit()


# TODO: remove me!
def place_on_hold(submission_id: int) -> None:
    """WARNING WARNING WARNING this is for testing purposes only."""
    dbss = events.services.classic._get_db_submission_rows(submission_id)
    i = events.services.classic._get_head_idx(dbss)
    head = dbss[i]
    session = events.services.classic.current_session()
    if head.is_published() or head.is_on_hold():
        return
    head.status = events.services.classic.models.Submission.ON_HOLD
    session.add(head)
    session.commit()
