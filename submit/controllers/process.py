"""
Controllers for process-related requests.
"""

from typing import Tuple, Dict, Any, Optional

from werkzeug import MultiDict
from werkzeug.exceptions import InternalServerError, BadRequest,\
    MethodNotAllowed

from flask import url_for

from arxiv import status
from ..services import compiler


logger = logging.getLogger(__name__)

Response = Tuple[Dict[str, Any], int, Dict[str, Any]]  # pylint: disable=C0103

def file_process(method: str, session: Session, submission_id: int, token: str) -> Response:
    """
    Begins a compilation.

    Parameters
    ----------
    method : str
        ``GET`` or ``POST``
    session : :class:`Session`
        The authenticated session for the request.
    submission_id : int
        The identifier of the submission for which the upload is being made.
    token : str
        The original (encrypted) auth token on the request. Used to perform
        subrequests to the file management service.

    Returns
    -------
    dict
        Response data, to render in template.
    int
        HTTP status code. This should be ``200`` or ``303``, unless something
        goes wrong.
    dict
        Extra headers to add/update on the response. This should include
        the `Location` header for use in the 303 redirect response, if
        applicable.
    """
    compiler.set_auth_token(token)
    compiler.request_compilation(submission_id)

    redirect = url_for('ui.file_upload', submission_id=submission_id)
    return {}, status.HTTP_303_SEE_OTHER, {'Location': redirect}
    