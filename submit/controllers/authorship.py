"""
Controller for verify_user action.

Creates an event of type `core.events.event.VerifyContactInformation`
"""

from typing import Tuple, Dict, Any

from wtforms import Form, BooleanField, RadioField
from wtforms.validators import InputRequired, ValidationError

from arxiv import status
from arxiv.base import logging
import events

# from arxiv-submission-core.events.event import VerifyContactInformation

logger = logging.getLogger(__name__)  # pylint: disable=C0103

Response = Tuple[Dict[str, Any], int, Dict[str, Any]]  # pylint: disable=C0103


def authorship(request_params: dict, submission_id: int) -> Response:
    """Convert authorship form data into an `AssertAuthorship` event."""
    form = AuthorshipForm(request_params)

    # Process event if go to next page
    action = request_params.get('action')
    if action in ['previous', 'save_exit', 'next'] and form.validate():
        # TODO: Create a concrete User event from cookie info.
        submitter = events.domain.User(1, email='ian413@cornell.edu',
                                       forename='Ima', surname='Nauthor')

        # Create AssertAuthorship event
        submission, stack = events.save(  # pylint: disable=W0612
            events.AssertAuthorship(creator=submitter),
            submission_id=submission_id
        )

        # TODO: Fix location header using url_for function
        if action == 'next':
            return {}, status.HTTP_303_SEE_OTHER,\
                {'Location': f'http://127.0.0.1:5000/license'}
        elif action == 'previous':
            return {}, status.HTTP_303_SEE_OTHER,\
                {'Location': f'http://127.0.0.1:5000/{submission_id}/verify_user'}
        elif action == 'save_exit':
            # TODO: correct with user portal page
            return {}, status.HTTP_303_SEE_OTHER,\
                {'Location': f'http://127.0.0.1:5000/'}

    # build response form
    response_data = dict()
    response_data['form'] = form
    logger.debug(f'verify_user data: {form}')
    response_data['submission_id'] = submission_id

    return response_data, status.HTTP_200_OK, {}


class AuthorshipForm(Form):
    """Generate form with radio button to confirm authorship information."""

    authorship = RadioField(choices=[('y', 'I am an author of this paper'),
                            ('n', 'I am not an author of this paper')],
                            validators=[InputRequired('Please choose one')])
    proxy = BooleanField('By checking this box, I certify that I have received \
                         authorization from arXiv to submit papers on behalf \
                         of the author(s).')

    def validate_authorship(self, field):
        """Require proxy field if submitter is not author."""
        if field.data == 'n' and not self.data.get('proxy'):
                raise ValidationError('You must get prior approval to submit \
                                        on behalf of authors')
