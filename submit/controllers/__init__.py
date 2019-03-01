"""Request controllers for the submission UI."""

from typing import Tuple, Dict, Any

from werkzeug import MultiDict

from arxiv import status
from arxiv.users.domain import Session

from .process import file_process, file_preview, compilation_log
from .upload import upload_files
from .upload import delete as delete_file
from .upload import delete_all as delete_all_files


from ..util import load_submission
from . import create, verify_user, authorship, license, policy, final, \
    classification, metadata, util, jref, withdraw, delete, cross
from .util import Response

__all__ = ('verify_user', 'authorship', 'license', 'policy', 'classification',
           'metadata', 'create', 'jref', 'delete', 'process')


def submission_status(method: str, params: MultiDict, session: Session,
                      submission_id: int) -> Response:
    user, client = util.user_and_client_from_session(session)

    # Will raise NotFound if there is no such submission.
    submission, submission_events = load_submission(submission_id)
    response_data = {
        'submission': submission,
        'submission_id': submission_id,
        'events': submission_events
    }
    return response_data, status.HTTP_200_OK, {}
