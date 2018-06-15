"""
Controller for verify_user action.

Creates an event of type `core.events.event.VerifyContactInformation`
"""

from typing import Tuple, Dict, Any, Optional

from werkzeug import MultiDict
from werkzeug.exceptions import InternalServerError, NotFound
from flask import url_for
from wtforms import Form, BooleanField
from wtforms.validators import InputRequired

from arxiv import status
from arxiv.base import logging
import events

from .util import flow_control, load_submission

logger = logging.getLogger(__name__)    #pylint: disable=C0103

Response = Tuple[Dict[str, Any], int, Dict[str, Any]]    #pylint: disable=C0103


def _create_submission(user: events.domain.User,
                       client: Optional[events.domain.Client] = None) \
        -> events.domain.Submission:
    """
    Create a new submission.

    Parameters
    ----------
    user : :class:`events.domain.User`
    client : :class:`events.domain.Client`

    Returns
    -------
    :class:`events.domain.Submission`

    Raises
    ------
    :class:`werkzeug.exceptions.NotFound`
        Raised when there is no submission with the specified ID.

    """
    try:
        submission, _ = events.save(
            events.CreateSubmission(creator=user, client=client)
        )
    except events.exceptions.InvalidStack as e:
        logger.error('Could not create submission: %s', e)
        # Creation requires basically no information, so this is
        # likely unrecoverable.
        raise InternalServerError('Creation failed') from e
    return submission


@flow_control('ui.user', 'ui.authorship', 'ui.user')
def verify_user(method: str, params: MultiDict,
                submission_id: Optional[int] = None) -> Response:
    """
    Prompt the user to verify their contact information.

    Generates a `VerifyContactInformation` event when valid data are POSTed.

    If a submission has not yet been created, the `CreateSubmission` event is
    raised to yield a submission_id.
    """
    logger.debug(f'method: {method}, submission: {submission_id}. {params}')

    if submission_id:
        # Will raise NotFound if there is no such submission.
        submission = load_submission(submission_id)

        # Initialize the form with the current state of the submission.
        if method == 'GET':
            params['verify_user'] = submission.submitter_contact_verified

    form = VerifyUserForm(params)
    response_data = {'submission_id': submission_id, 'form': form}

    # Process event if go to next page.
    if method == 'POST':
        if form.validate() and form.verify_user.data:
            logger.debug(f'Form is valid: {form.verify_user.data}')
            # TODO: Create a concrete User from cookie info.
            submitter = events.domain.User(1, email='ian413@cornell.edu',
                                           forename='Ima', surname='Nauthor')

            # Create submission if it does not yet exist.
            if submission_id is None:
                logger.debug('No submission ID; creating a new submission')
                submission = _create_submission(submitter)
                submission_id = submission.submission_id

            # Now that we have a submission, we can verify the user's contact
            # information.
            logger.debug('Submission ID: %s', str(submission_id))

            # There is no need to do this more than once.
            if not submission.submitter_contact_verified:
                try:    # Create VerifyContactInformation event
                    submission, _ = events.save(
                        events.VerifyContactInformation(creator=submitter),
                        submission_id=submission_id
                    )
                except events.exceptions.InvalidStack as e:
                    logger.error('Could not VerifyContactInformation: %s',
                                 str(e))
                    form.errors     # Causes the form to initialize errors.
                    form._errors['events'] = [ie.message for ie
                                              in e.event_exceptions]
                    return response_data, status.HTTP_400_BAD_REQUEST, {}

        # Either the form data were invalid, or the user did not check the
        # "verify" box.
        else:
            return response_data, status.HTTP_400_BAD_REQUEST, {}
        response_data.update({'submission_id': submission_id})
        return response_data, status.HTTP_303_SEE_OTHER, {}
    return response_data, status.HTTP_200_OK, {}


class VerifyUserForm(Form):
    """Generates form with single checkbox to confirm user information."""

    verify_user = BooleanField(
        'By checking this box, I verify that my user information is correct.',
        [InputRequired('Please confirm your user information')]
    )
