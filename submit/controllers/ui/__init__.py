"""Request controllers for the submission UI."""

from typing import Tuple, Dict, Any

from werkzeug import MultiDict

from http import HTTPStatus as status
from arxiv.users.domain import Session

from .new.process import file_process, file_preview, compilation_log
from .new.upload import upload_files
from .new.upload import delete as delete_file
from .new.upload import delete_all as delete_all_files

from .new import create, verify_user, authorship, license, policy, final,\
    classification, metadata, unsubmit

from . import  util, jref, withdraw, delete, cross

from submit.util import load_submission

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
    return response_data, status.OK, {}
