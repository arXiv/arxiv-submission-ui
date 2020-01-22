"""Request controllers for the submission UI."""

from typing import Tuple, Dict, Any

from werkzeug import MultiDict

from http import HTTPStatus as status
from arxiv.users.domain import Session

from . import util, jref, withdraw, delete, cross

# BDC34 I don't like this but it is so
# I can import ui into submit.routes and have routes
# named things like policy that are mapped to ui.policy
# If I import submit.controllers.ui.new.policy,
# then I'm trying to have two functions named policy.

from .new.authorship import authorship
from .new.classification import classification, cross_list
from .new.create import create
from .new.final import finalize
from .new.license import license
from .new.metadata import metadata
from .new.policy import policy
from .new.verify_user import verify
from .new.unsubmit import unsubmit

from .new import process
from .new import upload

from submit.util import load_submission
from submit.routes.ui.flow_control import ready_for_next, advance_to_current

from .util import Response


# def submission_status(method: str, params: MultiDict, session: Session,
#                       submission_id: int) -> Response:
#     user, client = util.user_and_client_from_session(session)

#     # Will raise NotFound if there is no such submission.
#     submission, submission_events = load_submission(submission_id)
#     response_data = {
#         'submission': submission,
#         'submission_id': submission_id,
#         'events': submission_events
#     }
#     return response_data, status.OK, {}


def submission_edit(method: str, params: MultiDict, session: Session,
                    submission_id: int) -> Response:
    """Cause flow_control to go to the current_stage of the Submission."""
    submission, submission_events = load_submission(submission_id)
    response_data = {
        'submission': submission,
        'submission_id': submission_id,
        'events': submission_events,
    }
    #
    return advance_to_current((response_data, status.OK, {}))
