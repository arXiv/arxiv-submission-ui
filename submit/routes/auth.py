"""Authorization helpers for :mod:`submit` application."""

from arxiv.users.domain import Session
from submit.util import load_submission


# TODO: when we get to the point where we need to support delegations, this
# will need to be updated.
def can_edit_submission(session: Session, submission_id: str, **kw) -> bool:
    """Check whether the user has privileges to edit a submission."""
    submission = load_submission(submission_id)
    return submission.owner.native_id == session.user.user_id