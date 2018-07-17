"""Controller for creating a new submission."""
from typing import Optional, Tuple, Dict, Any

from werkzeug import MultiDict
from werkzeug.exceptions import InternalServerError
from flask import url_for

from arxiv import status
from arxiv.base import logging
from arxiv.users.domain import Session, User

import arxiv.submission as events
from . import util

Response = Tuple[Dict[str, Any], int, Dict[str, Any]]   # pylint: disable=C0103

logger = logging.getLogger(__name__)    # pylint: disable=C0103


def create(method: str, params: MultiDict, session: Session) -> Response:
    """Create a new submission, and redirect to workflow."""
    if method == 'GET':     # Display a splash page.
        return {}, status.HTTP_200_OK, {}

    submitter, client = util.user_and_client_from_session(session)
    try:
        submission, _ = events.save(
            events.CreateSubmission(creator=submitter, client=client)
        )
    except events.exceptions.InvalidStack as e:
        logger.error('Could not create submission: %s', e)
        # Creation requires basically no information, so this is
        # likely unrecoverable.
        raise InternalServerError('Creation failed') from e

    submission_id = submission.submission_id
    target = url_for('ui.verify_user', submission_id=submission_id)
    return {}, status.HTTP_303_SEE_OTHER, {'Location': target}
