"""Authorization helpers for :mod:`submit` application."""

from arxiv.users.domain import Session
from submit.util import load_submission


# TODO: when we get to the point where we need to support delegations, this
# will need to be updated.
def can_edit(session: Session, submission_id: str, **kw) -> bool:
    """Check whether the user has privileges to edit a submission."""
    submission, submission_events = load_submission(submission_id)
    return str(submission.owner.native_id) == str(session.user.user_id)
