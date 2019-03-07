"""
Controller for classification actions.

Creates an event of type `core.events.event.SetPrimaryClassification`
Creates an event of type `core.events.event.AddSecondaryClassification`
"""
from typing import Tuple, Dict, Any, List, Optional
from werkzeug import MultiDict
from werkzeug.exceptions import InternalServerError
from flask import url_for, Markup
from wtforms import SelectField, widgets, HiddenField, validators

from arxiv import status, taxonomy
from arxiv.forms import csrf
from arxiv.base import logging, alerts
from arxiv.users.domain import Session
import arxiv.submission as events
from ..domain import SubmissionStage
from ..util import load_submission
from . import util

# from arxiv-submission-core.events.event import ConfirmContactInformation

logger = logging.getLogger(__name__)  # pylint: disable=C0103

Response = Tuple[Dict[str, Any], int, Dict[str, Any]]  # pylint: disable=C0103


class ClassificationForm(csrf.CSRFForm):
    """Form for classification selection."""

    CATEGORIES = [
        (archive['name'], [
            (category_id, f"{category['name']} ({category_id})")
            for category_id, category in taxonomy.CATEGORIES_ACTIVE.items()
            if category['in_archive'] == archive_id
        ])
        for archive_id, archive in taxonomy.ARCHIVES_ACTIVE.items()
    ]
    """Categories grouped by archive."""

    ADD = 'add'
    REMOVE = 'remove'
    OPERATIONS = [
        (ADD, 'Add'),
        (REMOVE, 'Remove')
    ]
    operation = HiddenField(default=ADD, validators=[validators.optional()])
    category = util.OptGroupSelectField('Category', choices=CATEGORIES,
                                        default='')

    def filter_choices(self, submission: events.domain.Submission,
                       session: Session) -> None:
        """Remove redundant choices, and limit to endorsed categories."""
        selected = self.category.data
        primary = submission.primary_classification

        choices = [
            (archive, [
                (category, display) for category, display in archive_choices
                if session.authorizations.endorsed_for(category)
                and (((primary is None or category != primary.category)
                      and category not in submission.secondary_categories)
                     or category == selected)
            ])
            for archive, archive_choices in self.category.choices
        ]
        self.category.choices = [
            (archive, _choices) for archive, _choices in choices
            if len(_choices) > 0
        ]

    @classmethod
    def formset(cls, submission: events.domain.Submission) \
            -> Dict[str, 'ClassificationForm']:
        """Generate a set of forms used to remove cross-list categories."""
        formset = {}
        if hasattr(submission, 'secondary_classification') and \
                submission.secondary_classification:
            for secondary in submission.secondary_classification:
                this_category = str(secondary.category)
                subform = cls(operation=cls.REMOVE, category=this_category)
                subform.category.widget = widgets.HiddenInput()
                formset[secondary.category] = subform
        return formset


def _data_from_submission(params: MultiDict,
                          submission: events.domain.Submission) -> MultiDict:
    if submission.primary_classification \
            and submission.primary_classification.category:
        params['category'] = submission.primary_classification.category
    return params


def classification(method: str, params: MultiDict, session: Session,
                   submission_id: int, **kwargs) -> Response:
    """Generate a `SetPrimaryClassification` event."""
    submitter, client = util.user_and_client_from_session(session)

    # Will raise NotFound if there is no such submission.
    submission, submission_events = load_submission(submission_id)

    # The form should be prepopulated based on the current state of the
    # submission.
    if method == 'GET':
        params = _data_from_submission(params, submission)
        if 'category' not in params:
            params['category'] = session.user.profile.default_category

    params['operation'] = ClassificationForm.ADD     # Always add a primary.

    form = ClassificationForm(params)
    # We want categories in dot-delimited "compound" format.

    form.filter_choices(submission, session)
    response_data = {
        'submission_id': submission_id,
        'form': form,
        'submission': submission,
        'submitter': submitter
    }

    if method == 'POST':
        if form.validate():
            logger.debug('Form is valid, with data: %s', str(form.data))
            category = form.category.data

            # If already selected, nothing more to do.
            if not submission.primary_classification \
                    or submission.primary_classification.category != category:
                try:
                    logger.debug('Setting new primary: %s', category)
                    # Create SetLicense event
                    submission, stack = events.save(  # pylint: disable=W0612
                        events.SetPrimaryClassification(creator=submitter,
                                                        category=category),
                        submission_id=submission_id
                    )
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


def cross_list(method: str, params: MultiDict, session: Session,
               submission_id: int, **kwargs) -> Response:
    """Generate an `AddSecondaryClassification` event."""
    submitter, client = util.user_and_client_from_session(session)

    # Will raise NotFound if there is no such submission.
    submission, submission_events = load_submission(submission_id)

    # We need forms for existing secondaries, to generate removal requests.
    formset = ClassificationForm.formset(submission)

    # This form handles additions and removals.
    form = ClassificationForm(params)
    form.operation._value = lambda: form.operation.data
    form.filter_choices(submission, session)
    _primary = taxonomy.CATEGORIES[submission.primary_classification.category]
    response_data = {
        'submission_id': submission_id,
        'form': form,
        'formset': formset,
        'primary': {
            'id': submission.primary_classification.category,
            'name': _primary['name']
        },

    }
    action = params.get('action')

    if method == 'POST':
        # Since the interface provides an "add" button to add cross-list
        # categories, we only want to handle the form data if the user is not
        # attempting to move to a different step.
        if not action:
            if form.validate():
                logger.debug('Form is valid, with data: %s', str(form.data))
                category = form.category.data
                operation = form.operation.data
                try:
                    if operation == ClassificationForm.REMOVE:
                        submission, _ = events.save(  # pylint: disable=W0612
                            events.RemoveSecondaryClassification(
                                creator=submitter,
                                category=category
                            ),
                            submission_id=submission_id
                        )
                    elif operation == ClassificationForm.ADD:
                        submission, _ = events.save(  # pylint: disable=W0612
                            events.AddSecondaryClassification(
                                creator=submitter,
                                category=category
                            ),
                            submission_id=submission_id
                        )
                except events.exceptions.InvalidStack as e:
                    logger.error('Could not add secondary: %s', str(e))
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

                # Re-build the formset, to reflect changes that we just made.
                response_data['formset'] = \
                    ClassificationForm.formset(submission)
                # We want a fresh form here, since the POSTed data should now
                # be reflected in the formset.
                form = ClassificationForm()
                form.operation._value = lambda: form.operation.data
                form.filter_choices(submission, session)
                response_data['form'] = form

                if len(submission.secondary_categories) > 3:
                    alerts.flash_warning(Markup(
                        'Adding more than three cross-list classifications'
                        ' will result in a delay in the acceptance of your'
                        ' submission.'
                    ))

            else:   # Form data were invalid.
                logger.debug('Invalid form data; return bad request')
                return response_data, status.HTTP_400_BAD_REQUEST, {}

    if action in ['previous', 'save_exit', 'next']:
        logger.debug('Redirect to %s', params.get('action'))
        return response_data, status.HTTP_303_SEE_OTHER, {}
    logger.debug('Nothing to do, return 200')
    return response_data, status.HTTP_200_OK, {}
