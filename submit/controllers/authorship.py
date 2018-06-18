"""
Controller for authorship action.

Creates an event of type `core.events.event.AssertAuthorship`
"""

from typing import Tuple, Dict, Any, Optional

from werkzeug import MultiDict
from werkzeug.exceptions import InternalServerError, NotFound

from flask import url_for
from wtforms import Form, BooleanField, RadioField
from wtforms.validators import InputRequired, ValidationError, optional

from arxiv import status
from arxiv.base import logging
import events

from .util import flow_control, load_submission

# from arxiv-submission-core.events.event import VerifyContactInformation

logger = logging.getLogger(__name__)  # pylint: disable=C0103

Response = Tuple[Dict[str, Any], int, Dict[str, Any]]  # pylint: disable=C0103


def _data_from_submission(params: MultiDict,
                          submission: events.domain.Submission) -> MultiDict:
    """Update form data based on the current state of the submission."""
    if submission.submitter_is_author is not None:
        params['authorship'] = (
            AuthorshipForm.YES if submission.submitter_is_author
            else AuthorshipForm.NO
        )
        # TODO: we should look at how we represent this on
        # events.domain.Submission.
        if submission.submitter_is_author is False:
            params['proxy'] = True
    return params


@flow_control('ui.verify_user', 'ui.license', 'ui.user')
def authorship(method: str, params: dict, submission_id: int,
               user: Optional[events.domain.User] = None,
               client: Optional[events.domain.Client] = None) -> Response:
    """Convert authorship form data into an `AssertAuthorship` event."""
    logger.debug(f'method: {method}, submission: {submission_id}. {params}')

    # TODO: Create a concrete User from cookie info.
    user = events.domain.User(1, email='ian413@cornell.edu',
                              forename='Ima', surname='Nauthor')

    # Will raise NotFound if there is no such submission.
    submission = load_submission(submission_id)

    # The form should be prepopulated based on the current state of the
    # submission.
    if method == 'GET':
        params = _data_from_submission(params, submission)

    form = AuthorshipForm(params)
    response_data = {'submission_id': submission_id, 'form': form}

    if method == 'POST':
        if form.validate():
            logger.debug('Form is valid, with data: %s', str(form.data))
            value = (form.authorship.data == form.YES)

            # No need to do this more than once.
            if submission.submitter_is_author != value:
                try:
                    # Create AssertAuthorship event
                    submission, stack = events.save(  # pylint: disable=W0612
                        events.AssertAuthorship(
                            creator=user,
                            client=client,
                            submitter_is_author=value
                        ),
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


class AuthorshipForm(Form):
    """Generate form with radio button to confirm authorship information."""

    YES = 'y'
    NO = 'n'

    authorship = RadioField(choices=[(YES, 'I am an author of this paper'),
                                     (NO, 'I am not an author of this paper')],
                            validators=[InputRequired('Please choose one')])
    proxy = BooleanField('By checking this box, I certify that I have '
                         'received authorization from arXiv to submit papers '
                         'on behalf of the author(s).',
                         validators=[optional()])

    def validate_authorship(self, field):
        """Require proxy field if submitter is not author."""
        if field.data == self.NO and not self.data.get('proxy'):
                raise ValidationError('You must get prior approval to submit '
                                      'on behalf of authors')
