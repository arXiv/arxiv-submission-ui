"""
Controller for policy action.

Creates an event of type `core.events.event.AcceptPolicy`
"""

from typing import Tuple, Dict, Any

from werkzeug import MultiDict
from werkzeug.exceptions import InternalServerError
from flask import url_for
from wtforms import Form, BooleanField
from wtforms.validators import InputRequired

from arxiv import status
from arxiv.base import logging
import events
from .util import flow_control, load_submission

# from arxiv-submission-core.events.event import AcceptPolicy

logger = logging.getLogger(__name__)  # pylint: disable=C0103

Response = Tuple[Dict[str, Any], int, Dict[str, Any]]  # pylint: disable=C0103


@flow_control('ui.license', 'ui.classification', 'ui.user')
def policy(method: str, params: MultiDict, submission_id: int) -> Response:
    """Convert policy form data into an `AcceptPolicy` event."""
    logger.debug(f'method: {method}, submission: {submission_id}. {params}')
    submission = load_submission(submission_id)
    form = PolicyForm(params)
    response_data = {'submission_id': submission_id, 'form': form}

    # TODO: Create a concrete User event from cookie info.
    submitter = events.domain.User(1, email='ian413@cornell.edu',
                                   forename='Ima', surname='Nauthor')

    if method == 'GET':
        params['policy'] = submission.submitter_accepts_policy

    if method == 'POST':
        if form.validate():
            logger.debug('Form is valid, with data: %s', str(form.data))
            accept_policy = form.policy.data
            if accept_policy and not submission.submitter_accepts_policy:
                try:
                    # Create AcceptPolicy event
                    submission, stack = events.save(  # pylint: disable=W0612
                        events.AcceptPolicy(creator=submitter),
                        submission_id=submission_id
                    )
                except events.exceptions.InvalidStack as e:
                    logger.error('Could not AssertAuthorship: %s', str(e))
                    form.errors     # Causes the form to initialize errors.
                    form._errors['events'] = [ie.message for ie
                                              in e.event_exceptions]
                    return response_data, status.HTTP_400_BAD_REQUEST, {}
                except events.exceptions.SaveError as e:
                    logger.error('Could not save primary event')
                    raise InternalServerError(
                        'There was a problem saving this operation'
                    ) from e
                if params.get('action') in ['previous', 'save_exit', 'next']:
                    return response_data, status.HTTP_303_SEE_OTHER, {}

        else:   # Form data were invalid.
            return response_data, status.HTTP_400_BAD_REQUEST, {}

    return response_data, status.HTTP_200_OK, {}


class PolicyForm(Form):
    """Generate form with checkbox to confirm policy."""

    policy = BooleanField(
        'By checking this box, I agree to the policies listed on this page.',
        [InputRequired('Please check the box to agree to the policies')]
    )
