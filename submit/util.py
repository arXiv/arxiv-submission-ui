"""Utilities and helpers for the :mod:`submit` application."""

from werkzeug.exceptions import NotFound
import arxiv.submission as events


def load_submission(submission_id: int) -> events.domain.Submission:
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
    try:
        submission, _ = events.load(submission_id)
    except events.exceptions.NoSuchSubmission as e:
        raise NotFound('No such submission.') from e
    return submission
