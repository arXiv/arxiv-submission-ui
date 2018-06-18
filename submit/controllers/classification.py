"""
Controller for classification actinos.

Creates an event of type `core.events.event.SetPrimaryClassification`
Creates an event of type `core.events.event.AddSecondaryClassification`
"""
from typing import Tuple, Dict, Any
from werkzeug import MultiDict
from werkzeug.exceptions import InternalServerError
from flask import url_for
from wtforms import Form

from arxiv import status, taxonomy
from arxiv.base import logging
import events
from .util import flow_control, OptGroupSelectField, load_submission

# from arxiv-submission-core.events.event import VerifyContactInformation

logger = logging.getLogger(__name__)  # pylint: disable=C0103

Response = Tuple[Dict[str, Any], int, Dict[str, Any]]  # pylint: disable=C0103


def _data_from_submission(params: MultiDict,
                          submission: events.domain.Submission) -> MultiDict:
    if submission.primary_classification \
            and submission.primary_classification.category:
        params['category'] = submission.primary_classification.category
    return params


@flow_control('ui.policy', 'ui.crosslist', 'ui.user')
def classification(method: str, params: MultiDict,
                   submission_id: int) -> Response:
    """Generate a `SetPrimaryClassification` event."""
    # TODO: Create a concrete User from cookie info.
    submitter = events.domain.User(1, email='ian413@cornell.edu',
                                   forename='Ima', surname='Nauthor')

    # Will raise NotFound if there is no such submission.
    submission = load_submission(submission_id)

    # The form should be prepopulated based on the current state of the
    # submission.
    if method == 'GET':
        params = _data_from_submission(params, submission)

    form = PrimaryClassificationForm(params)
    response_data = {'submission_id': submission_id, 'form': form}

    if method == 'POST':
        if form.validate():
            logger.debug('Form is valid, with data: %s', str(form.data))
            category = form.category.data

            # If already selected, nothing more to do.
            if not submission.primary_classification \
                    or submission.primary_classification.category != category:
                try:
                    logger.debug('Setting new primary: %s', category)
                    # Create SelectLicense event
                    submission, stack = events.save(  # pylint: disable=W0612
                        events.SetPrimaryClassification(creator=submitter,
                                                        category=category),
                        submission_id=submission_id
                    )
                    print(submission.primary_classification)
                except events.exceptions.InvalidStack as e:
                    logger.error('Could not set primary: %s', str(e))
                    form.errors     # Causes the form to initialize errors.
                    form._errors['events'] = [ie.message for ie
                                              in e.event_exceptions]
                    logger.debug('InvalidStack; return bad request')
                    return response_data, status.HTTP_400_BAD_REQUEST, {}
                except events.exceptions.SaveError as e:
                    logger.error('Could not save primary event')
                    raise InternalServerError(
                        'There was a problem saving this operation'
                    ) from e
        else:   # Form data were invalid.
            logger.debug('Invalid form data; return bad request')
            return response_data, status.HTTP_400_BAD_REQUEST, {}
        if params.get('action') in ['previous', 'save_exit', 'next']:
            logger.debug('Redirect to %s', params.get('action'))
            return response_data, status.HTTP_303_SEE_OTHER, {}
    logger.debug('Nothing to do, return 200')
    return response_data, status.HTTP_200_OK, {}


@flow_control('ui.classification', 'ui.upload', 'ui.user')
def crosslist(params: dict, submission_id: int) -> Response:
    """Generate a `AddSecondaryClassification` event."""
    form = SecondaryClassificationForm(params)

    # Process event if go to next page
    action = params.get('action')
    if action in ['previous', 'save_exit', 'next'] and form.validate():
        # TODO: Write submission info
        pass

    # build response form
    response_data = {'form': form, 'submission_id': submission_id}
    logger.debug(f'verify_user data: {form}')

    return response_data, status.HTTP_200_OK, {}


class PrimaryClassificationForm(Form):
    """Form for primary classification selection."""

    CATEGORIES = [
        (archive['name'], [
            (category_id, f"{category['name']} ({category_id})")
            for category_id, category in taxonomy.CATEGORIES.items()
            if category['is_active'] and category['in_archive'] == archive_id
        ])
        for archive_id, archive in taxonomy.ARCHIVES.items()
        if 'end_date' not in archive
    ]
    """Categories grouped by archive."""

    category = OptGroupSelectField('Primary category', choices=CATEGORIES,
                                   default='')


class SecondaryClassificationForm(Form):
    """Form for secondary classification selection"""
