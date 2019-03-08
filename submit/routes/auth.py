"""Authorization helpers for :mod:`submit` application."""

from arxiv.users.domain import Session
from submit.util import load_submission

from arxiv.base import logging

logger = logging.getLogger(__name__)
logger.propagate = False


# TODO: when we get to the point where we need to support delegations, this
# will need to be updated.
def is_owner(session: Session, submission_id: str, **kw) -> bool:
    """Check whether the user has privileges to edit a submission."""
    submission, submission_events = load_submission(submission_id)
    logger.debug('Submission owned by %s; request is from %s',
                 str(submission.owner.native_id),
                 str(session.user.user_id))
    return str(submission.owner.native_id) == str(session.user.user_id)
