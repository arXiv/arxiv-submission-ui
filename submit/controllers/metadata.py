"""Provides a controller for updating metadata on a submission."""

from typing import Tuple, Dict, Any, List

from werkzeug import MultiDict
from werkzeug.exceptions import InternalServerError
from flask import url_for
from wtforms import Form
from wtforms.fields import TextField, TextAreaField, Field
from wtforms import validators

from arxiv import status
from arxiv.base import logging
from arxiv.users.domain import Session
import arxiv.submission as events

from ..util import load_submission
from . import util

logger = logging.getLogger(__name__)  # pylint: disable=C0103

Response = Tuple[Dict[str, Any], int, Dict[str, Any]]  # pylint: disable=C0103


class CoreMetadataForm(Form, util.FieldMixin, util.SubmissionMixin):
    """Handles core metadata fields on a submission."""

    title = TextField('*Title', validators=[validators.DataRequired()])
    authors_display = TextAreaField(
        '*Authors',
        validators=[validators.DataRequired()],
        description=(
            "use <code>GivenName(s) FamilyName(s)</code> or <code>I. "
            "FamilyName</code>; separate individual authors with "
            "a comma or 'and'."
        )
    )
    abstract = TextAreaField('*Abstract',
                             validators=[validators.DataRequired()],
                             description='Limit of 1920 characters')
    comments = TextField('Comments',
                         default='',
                         validators=[validators.optional()],
                         description=(
                            "Supplemental information such as number of pages "
                            "or figures, conference information."
                         ))

    def validate_title(form: Form, field: Field) -> None:
        """Validate title input using core events."""
        if field.data == form.submission.metadata.title:     # Nothing to do.
            return
        if field.data:
            form._validate_event(events.SetTitle, title=field.data)

    def validate_abstract(form: Form, field: Field) -> None:
        """Validate abstract input using core events."""
        if field.data == form.submission.metadata.abstract:    # Nothing to do.
            return
        if field.data:
            form._validate_event(events.SetAbstract, abstract=field.data)

    def validate_comments(form: Form, field: Field) -> None:
        """Validate comments input using core events."""
        if field.data == form.submission.metadata.comments:    # Nothing to do.
            return
        if field.data is not None:
            form._validate_event(events.SetComments, comments=field.data)

    def validate_authors_display(form: Form, field: Field) -> None:
        """Validate authors input using core events."""
        if field.data == form.submission.metadata.authors_display:
            return
        if field.data:
            form._validate_event(events.UpdateAuthors,
                                 authors_display=field.data)


class OptionalMetadataForm(Form, util.FieldMixin, util.SubmissionMixin):
    """Handles optional metadata fields on a submission."""

    doi = TextField('DOI',
                    validators=[validators.optional()],
                    description="Full DOI of the version of record.")
    journal_ref = TextField('Journal reference',
                            validators=[validators.optional()],
                            description=(
                                "See <a href='https://arxiv.org/help/jref'>"
                                "the arXiv help pages</a> for details."
                            ))
    report_num = TextField('Report number',
                           validators=[validators.optional()],
                           description=(
                               "See <a href='https://arxiv.org/help/jref'>"
                               "the arXiv help pages</a> for details."
                           ))
    acm_class = TextField('ACM classification',
                          validators=[validators.optional()],
                          description="example: F.2.2; I.2.7")

    msc_class = TextField('MSC classification',
                          validators=[validators.optional()],
                          description=("example: 14J60 (Primary), 14F05, "
                                       "14J26 (Secondary)"))

    def validate_doi(form: Form, field: Field) -> None:
        """Validate DOI input using core events."""
        if field.data == form.submission.metadata.doi:     # Nothing to do.
            return
        if field.data:
            form._validate_event(events.SetDOI, doi=field.data)

    def validate_journal_ref(form: Form, field: Field) -> None:
        """Validate journal reference input using core events."""
        if field.data == form.submission.metadata.journal_ref:
            return
        if field.data:
            form._validate_event(events.SetJournalReference,
                                 journal_ref=field.data)

    def validate_report_num(form: Form, field: Field) -> None:
        """Validate report number input using core events."""
        if field.data == form.submission.metadata.report_num:
            return
        if field.data:
            form._validate_event(events.SetReportNumber,
                                 report_num=field.data)

    def validate_acm_class(form: Form, field: Field) -> None:
        """Validate ACM classification input using core events."""
        if field.data == form.submission.metadata.acm_class:
            return
        if field.data:
            form._validate_event(events.SetACMClassification,
                                 acm_class=field.data)

    def validate_msc_class(form: Form, field: Field) -> None:
        """Validate MSC classification input using core events."""
        if field.data == form.submission.metadata.msc_class:
            return
        if field.data:
            form._validate_event(events.SetMSCClassification,
                                 msc_class=field.data)


def _data_from_submission(params: MultiDict, submission: events.Submission,
                          form_class: type) -> MultiDict:
    if not submission.metadata:
        return params
    for field in form_class.fields():
        params[field] = getattr(submission.metadata, field, '')
    return params


@util.flow_control('ui.file_process', 'ui.add_optional_metadata', 'ui.user')
def metadata(method: str, params: MultiDict, session: Session,
             submission_id: int) -> Response:
    """Update metadata on the submission."""
    submitter, client = util.user_and_client_from_session(session)
    logger.debug(f'method: {method}, submission: {submission_id}. {params}')

    # Will raise NotFound if there is no such submission.
    submission = load_submission(submission_id)
    # The form should be prepopulated based on the current state of the
    # submission.
    if method == 'GET':
        params = _data_from_submission(params, submission, CoreMetadataForm)

    form = CoreMetadataForm(params)
    form.submission = submission
    form.creator = submitter
    response_data = {'submission_id': submission_id, 'form': form}

    if method == 'POST':
        if not form.validate():
            logger.debug('Invalid form data; return bad request')
            return response_data, status.HTTP_400_BAD_REQUEST, {}

        logger.debug('Form is valid, with data: %s', str(form.data))

        # We only want to apply an UpdateMetadata if the metadata has
        # actually changed.
        if form.events:   # Metadata has changed.
            try:
                # Save the events created during form validation.
                submission, stack = events.save(
                    *form.events,
                    submission_id=submission_id
                )
            except events.exceptions.InvalidStack as e:
                logger.error('Could not update metadata: %s', str(e))
                form.errors     # Causes the form to initialize errors.
                form._errors['events'] = [ie.message for ie
                                          in e.event_exceptions]
                logger.debug('InvalidStack; return bad request')
                return response_data, status.HTTP_400_BAD_REQUEST, {}
            except events.exceptions.SaveError as e:
                logger.error('Could not save metadata event')
                raise InternalServerError(
                    'There was a problem saving this operation'
                ) from e
    if params.get('action') in ['previous', 'save_exit', 'next']:
        logger.debug('Redirect to %s', params.get('action'))
        return response_data, status.HTTP_303_SEE_OTHER, {}
    logger.debug('Nothing to do, return 200')
    return response_data, status.HTTP_200_OK, {}


@util.flow_control('ui.add_metadata', 'ui.confirm_submit', 'ui.user')
def optional(method: str, params: MultiDict, session: Session,
             submission_id: int) -> Response:
    """Update optional metadata on the submission."""
    submitter, client = util.user_and_client_from_session(session)

    logger.debug(f'method: {method}, submission: {submission_id}. {params}')

    # Will raise NotFound if there is no such submission.
    submission = load_submission(submission_id)
    # The form should be prepopulated based on the current state of the
    # submission.
    if method == 'GET':
        params = _data_from_submission(params, submission,
                                       OptionalMetadataForm)

    form = OptionalMetadataForm(params)
    form.submission = submission
    form.creator = submitter
    response_data = {'submission_id': submission_id, 'form': form}

    if method == 'POST':
        if not form.validate():
            logger.debug('Invalid form data; return bad request')
            return response_data, status.HTTP_400_BAD_REQUEST, {}

        logger.debug('Form is valid, with data: %s', str(form.data))

        # We only want to apply an UpdateMetadata if the metadata has
        # actually changed.
        if form.events:   # Metadata has changed.
            try:
                # Create UpdateMetadata event
                submission, stack = events.save(
                    *form.events,
                    submission_id=submission_id
                )
            except events.exceptions.InvalidStack as e:
                logger.error('Could not update metadata: %s', str(e))
                form.errors     # Causes the form to initialize errors.
                form._errors['events'] = [ie.message for ie
                                          in e.event_exceptions]
                logger.debug('InvalidStack; return bad request')
                return response_data, status.HTTP_400_BAD_REQUEST, {}
            except events.exceptions.SaveError as e:
                logger.error('Could not save metadata event')
                raise InternalServerError(
                    'There was a problem saving this operation'
                ) from e
    if params.get('action') in ['previous', 'save_exit', 'next']:
        logger.debug('Redirect to %s', params.get('action'))
        return response_data, status.HTTP_303_SEE_OTHER, {}
    logger.debug('Nothing to do, return 200')
    return response_data, status.HTTP_200_OK, {}
