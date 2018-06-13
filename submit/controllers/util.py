"""Helpers for controllers."""

from typing import Callable, Any, Dict, Tuple, Optional
from werkzeug import MultiDict
from flask import url_for
from arxiv import status

Response = Tuple[Dict[str, Any], int, Dict[str, Any]]  # pylint: disable=C0103


# TODO: handle case that there is no prev/next page!
# TODO: handle case that prev/next page doesn't exist.
def flow_control(prev_page: str, next_page: str, exit_page: str) -> Callable:
    """Get a decorator that handles redirection to next/previous steps."""
    def deco(func: Callable) -> Callable:
        """Decorator that applies next/previous redirection."""
        def wrapper(params: MultiDict, *args: Any, **kwargs: Dict) -> Response:
            """Update the redirect to the next, previous, or exit page."""
            data, status_code, headers = func(params, *args, **kwargs)
            # No redirect; nothing to do.
            if status_code != status.HTTP_303_SEE_OTHER:
                return data, status_code, headers
            action = params.get('action')
            # Get the submission ID from the response, since it may not have
            # been a param for the controller.
            submission_id = data.get('submission_id')

            def _get_target(page: str) -> str:
                if submission_id:
                    return url_for(page, submission_id=submission_id)
                return url_for(page)

            if action == 'next':
                headers.update({'Location': _get_target(next_page)})
            elif action == 'previous':
                headers.update({'Location': _get_target(prev_page)})
            elif action == 'save_exit':
                headers.update({'Location': _get_target(exit_page)})
            print('!!')
            return data, status_code, headers
        return wrapper
    return deco
