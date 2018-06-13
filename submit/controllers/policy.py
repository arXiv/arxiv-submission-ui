"""
Controller for policy action.

Creates an event of type `core.events.event.AcceptPolicy`
"""

from typing import Tuple, Dict, Any

from flask import url_for
from wtforms import Form, BooleanField
from wtforms.validators import InputRequired

from arxiv import status
from arxiv.base import logging
import events
from .util import flow_control

# from arxiv-submission-core.events.event import AcceptPolicy

logger = logging.getLogger(__name__)  # pylint: disable=C0103

Response = Tuple[Dict[str, Any], int, Dict[str, Any]]  # pylint: disable=C0103


@flow_control('ui.license', 'ui.classification', 'ui.user')
def policy(request_params: dict, submission_id: int) -> Response:
    """Convert policy form data into an `AcceptPolicy` event."""
    form = PolicyForm(request_params)
    response_data = {'submission_id': submission_id}

    # Process event if go to next page
    action = request_params.get('action')
    if action in ['previous', 'save_exit', 'next'] and form.validate():
        # TODO: Create a concrete User event from cookie info.
        submitter = events.domain.User(1, email='ian413@cornell.edu',
                                       forename='Ima', surname='Nauthor')

        # Create AcceptPolicy event
        submission, stack = events.save(  # pylint: disable=W0612
            events.AcceptPolicy(creator=submitter),
            submission_id=submission_id
        )
        return response_data, status.HTTP_303_SEE_OTHER, {}

    # build response form
    response_data.update({'form': form})
    logger.debug(f'policy data: {form}')
    return response_data, status.HTTP_200_OK, {}


class PolicyForm(Form):
    """Generate form with checkbox to confirm policy."""

    policy = BooleanField(
        'By checking this box, I agree to the policies listed on this page.',
        [InputRequired('Please check the box to agree to the policies')]
    )
