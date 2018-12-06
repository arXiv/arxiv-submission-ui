"""Controller for cross-list requests."""

from typing import Tuple, Dict, Any, Optional, List

from werkzeug import MultiDict
from werkzeug.exceptions import InternalServerError, NotFound

from flask import url_for, Markup
from wtforms import Form, widgets
from wtforms.fields import Field, BooleanField, HiddenField
from wtforms.validators import InputRequired, ValidationError, optional, \
    DataRequired

from arxiv import status
from arxiv.taxonomy import CATEGORIES_ACTIVE as CATEGORIES
from arxiv.taxonomy import ARCHIVES_ACTIVE as ARCHIVES
from arxiv.base import logging, alerts
from arxiv.forms import csrf
from arxiv.users.domain import Session
import arxiv.submission as events

from ..util import load_submission
from . import util

logger = logging.getLogger(__name__)  # pylint: disable=C0103

Response = Tuple[Dict[str, Any], int, Dict[str, Any]]  # pylint: disable=C0103


CONTACT_SUPPORT = Markup(
    'If you continue to experience problems, please contact'
    ' <a href="mailto:help@arxiv.org"> arXiv support</a>.'
)


class HiddenListField(HiddenField):
    def process_formdata(self, valuelist):
        self.data = list(str(x) for x in valuelist if x)

    def process_data(self, value):
        try:
            self.data = list(str(v) for v in value if v)
        except (ValueError, TypeError):
            self.data = None

    def _value(self):
        return ",".join(self.data) if self.data else ""


class CrossListForm(csrf.CSRFForm):
    """Submit a cross-list request."""

    CATEGORIES = [
        (archive['name'], [
            (category_id, f"{category['name']} ({category_id})")
            for category_id, category in CATEGORIES.items()
            if category['in_archive'] == archive_id
        ])
        for archive_id, archive in ARCHIVES.items()
    ]
    """Categories grouped by archive."""

    ADD = 'add'
    REMOVE = 'remove'
    OPERATIONS = [
        (ADD, 'Add'),
        (REMOVE, 'Remove')
    ]
    operation = HiddenField(default=ADD, validators=[optional()])
    category = util.OptGroupSelectField('Category', choices=CATEGORIES,
                                        default='', validators=[optional()])
    selected = HiddenListField()
    confirmed = BooleanField('Confirmed',
                             false_values=('false', False, 0, '0', ''))

    def validate_selected(form: csrf.CSRFForm, field: Field) -> None:
        if form.confirmed.data and not field.data:
            raise ValidationError('Please select a category')
        for value in field.data:
            if value not in CATEGORIES:
                raise ValidationError('Not a valid category')

    def validate_category(form: csrf.CSRFForm, field: Field) -> None:
        if not form.confirmed.data and not field.data:
            raise ValidationError('Please select a category')

    def filter_choices(self, submission: events.domain.Submission,
                       session: Session,
                       exclude: Optional[List[str]] = None) -> None:
        """Remove redundant choices, and limit to endorsed categories."""
        selected: List[str] = self.category.data
        primary = submission.primary_classification

        choices = [
            (archive, [
                (category, display) for category, display in archive_choices
                if (exclude is not None and category not in exclude
                    and (primary is None or category != primary.category)
                    and category not in submission.secondary_categories)
                or category in selected
            ])
            for archive, archive_choices in self.category.choices
        ]
        self.category.choices = [
            (archive, _choices) for archive, _choices in choices
            if len(_choices) > 0
        ]

    @classmethod
    def formset(cls, selected: List[str]) -> Dict[str, 'CrossListForm']:
        """Generate a set of forms to add/remove categories in the template."""
        formset = {}
        for category in selected:
            if not category:
                continue
            subform = cls(operation=cls.REMOVE, category=category)
            subform.category.widget = widgets.HiddenInput()
            formset[category] = subform
        return formset


def request_cross(method: str, params: MultiDict, session: Session,
                  submission_id: int) -> Response:
    """Request cross-list classification for an announced e-print."""
    submitter, client = util.user_and_client_from_session(session)
    logger.debug(f'method: {method}, submission: {submission_id}. {params}')

    # Will raise NotFound if there is no such submission.
    submission, submission_events = load_submission(submission_id)

    # The submission must be published for this to be a withdrawal request.
    if not submission.published:
        alerts.flash_failure(
            Markup("Submission must first be published. See <a"
                   " href='https://arxiv.org/help/withdraw'>the arXiv help"
                   " pages</a> for details."))
        status_url = url_for('ui.create_submission')
        return {}, status.HTTP_303_SEE_OTHER, {'Location': status_url}

    if method == 'GET':
        params = MultiDict({})

    params.setdefault("confirmed", False)
    params.setdefault("operation", CrossListForm.ADD)
    form = CrossListForm(params)
    selected = [v for v in form.selected.data if v]
    form.filter_choices(submission, session, exclude=selected)

    response_data = {
        'submission_id': submission_id,
        'submission': submission,
        'form': form,
        'selected': selected,
        'formset': CrossListForm.formset(selected)
    }
    if submission.primary_classification:
        response_data['primary'] = \
            CATEGORIES[submission.primary_classification.category]

    if method == 'POST':
        if not form.validate():
            return response_data, status.HTTP_400_BAD_REQUEST, {}
        if form.confirmed.data:     # Stop adding new categories, and submit.
            response_data['form'].operation.data = CrossListForm.ADD
            response_data['require_confirmation'] = True

            try:    # Submit the cross-list request.
                events.save(
                    events.RequestCrossList(creator=submitter, client=client,
                                            categories=form.selected.data),
                    submission_id=submission_id
                )
            except events.exceptions.InvalidEvent as e:
                # Since we're doing validation on the form, this should only
                # happen if the user really monkeys with the request or if we
                # have a programming error.
                logger.error('Cross request made with bad category: %s', e)
                alerts.flash_failure(Markup(
                    "There was a problem with your request. Please try again."
                    f" {CONTACT_SUPPORT}"
                ))
                return response_data, status.HTTP_400_BAD_REQUEST, {}
            except events.exceptions.SaveError as e:
                # This would be due to a database error, or something else
                # that likely isn't the user's fault.
                logger.error('Could not save cross list request event')
                alerts.flash_failure(Markup(
                    "There was a problem processing your request. Please try"
                    f" again. {CONTACT_SUPPORT}"
                ))
                return response_data, status.HTTP_400_BAD_REQUEST, {}

            # Success! Send user back to the submission page.
            alerts.flash_success("Cross-list request submitted.")
            status_url = url_for('ui.create_submission')
            return {}, status.HTTP_303_SEE_OTHER, {'Location': status_url}
        else:   # User is adding or removing a category.
            if form.operation.data:
                if form.operation.data == CrossListForm.REMOVE:
                    selected.remove(form.category.data)
                elif form.operation.data == CrossListForm.ADD:
                    selected.append(form.category.data)
                # Update the "remove" formset to reflect the change.
                response_data['formset'] = CrossListForm.formset(selected)
                response_data['selected'] = selected
            # Now that we've handled the request, get a fresh form for adding
            # more categories or submitting the request.
            response_data['form'] = CrossListForm()
            response_data['form'].filter_choices(submission, session,
                                                 exclude=selected)
            response_data['form'].operation.data = CrossListForm.ADD
            response_data['require_confirmation'] = True
            return response_data, status.HTTP_200_OK, {}
    return response_data, status.HTTP_200_OK, {}
