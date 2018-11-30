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
    session = events.services.classic.current_session()
    db_submission = session.query(events.services.classic.models.Submission) \
        .get(submission_id)
    if db_submission.doc_paper_id:
        db_submission_ = session.query(events.services.classic.models.Submission) \
            .filter(events.services.classic.models.Submission.doc_paper_id == db_submission.doc_paper_id) \
            .filter(events.services.classic.models.Submission.type != events.services.classic.models.Submission.JOURNAL_REFERENCE) \
            .order_by(events.services.classic.models.Submission.submission_id.desc()) \
            .first()
        db_submission = db_submission_ if db_submission_ else db_submission
    if db_submission.is_published():
        return
    db_submission.status = events.services.classic.models.Submission.PUBLISHED
    paper_id = datetime.now().strftime('%s')[-4:] \
        + "." \
        + datetime.now().strftime('%s')[-5:]
    db_document = events.services.classic.models.Document(paper_id=paper_id)
    db_submission.doc_paper_id = paper_id
    db_submission.document = db_document
    session.add(db_submission)
    session.add(db_document)
    session.commit()
