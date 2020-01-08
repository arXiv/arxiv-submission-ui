"""Provides a controller for updating metadata on a submission."""

from typing import Tuple, Dict, Any, List

from werkzeug import MultiDict
from werkzeug.exceptions import InternalServerError, BadRequest
from wtforms.fields import TextField, TextAreaField, Field
from wtforms import validators

from http import HTTPStatus as status
from arxiv.forms import csrf
from arxiv.base import logging
from arxiv.users.domain import Session
from arxiv.submission import save, SaveError, Submission, User, Client, Event
from arxiv.submission.domain.event import SetTitle, SetAuthors, SetAbstract, \
    SetACMClassification, SetMSCClassification, SetComments, SetReportNumber, \
    SetJournalReference, SetDOI

from submit.util import load_submission
from submit.controllers.ui.util import validate_command, FieldMixin, user_and_client_from_session

logger = logging.getLogger(__name__)  # pylint: disable=C0103

Response = Tuple[Dict[str, Any], int, Dict[str, Any]]  # pylint: disable=C0103


class CoreMetadataForm(csrf.CSRFForm, FieldMixin):
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


class OptionalMetadataForm(csrf.CSRFForm, FieldMixin):
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


def _data_from_submission(params: MultiDict, submission: Submission,
                          form_class: type) -> MultiDict:
    if not submission.metadata:
        return params
    for field in form_class.fields():
        params[field] = getattr(submission.metadata, field, '')
    return params


def metadata(method: str, params: MultiDict, session: Session,
             submission_id: int, **kwargs) -> Response:
    """Update metadata on the submission."""
    submitter, client = user_and_client_from_session(session)
    logger.debug(f'method: {method}, submission: {submission_id}. {params}')

    # Will raise NotFound if there is no such submission.
    submission, submission_events = load_submission(submission_id)
    # The form should be prepopulated based on the current state of the
    # submission.
    if method == 'GET':
        params = _data_from_submission(params, submission, CoreMetadataForm)

    form = CoreMetadataForm(params)
    response_data = {
        'submission_id': submission_id,
        'form': form,
        'submission': submission
    }

    if method == 'POST':
        if not form.validate():
            raise BadRequest(response_data)

        logger.debug('Form is valid, with data: %s', str(form.data))

        commands, valid = _commands(form, submission, submitter, client)
        # We only want to apply an UpdateMetadata if the metadata has
        # actually changed.
        if commands:   # Metadata has changed.
            if not all(valid):
                logger.debug('Not all commands are valid')
                response_data['form'] = form
                raise BadRequest(response_data)

            try:
                # Save the events created during form validation.
                submission, _ = save(*commands, submission_id=submission_id)
            except SaveError as e:
                raise InternalServerError(response_data) from e
            response_data['submission'] = submission

    if params.get('action') in ['previous', 'save_exit', 'next']:
        return response_data, status.SEE_OTHER, {}
    return response_data, status.OK, {}


def optional(method: str, params: MultiDict, session: Session,
             submission_id: int, **kwargs) -> Response:
    """Update optional metadata on the submission."""
    submitter, client = user_and_client_from_session(session)

    logger.debug(f'method: {method}, submission: {submission_id}. {params}')

    # Will raise NotFound if there is no such submission.
    submission, submission_events = load_submission(submission_id)
    # The form should be prepopulated based on the current state of the
    # submission.
    if method == 'GET':
        params = _data_from_submission(params, submission,
                                       OptionalMetadataForm)

    form = OptionalMetadataForm(params)
    response_data = {
        'submission_id': submission_id,
        'form': form,
        'submission': submission
    }

    if method == 'POST':
        if not form.validate():
            raise BadRequest(response_data)

        logger.debug('Form is valid, with data: %s', str(form.data))

        commands, valid = _opt_commands(form, submission, submitter, client)
        # We only want to apply updates if the metadata has actually changed.
        if commands:   # Metadata has changed.
            if not all(valid):
                raise BadRequest(response_data)

            try:
                submission, _ = save(*commands, submission_id=submission_id)
            except SaveError as e:
                raise InternalServerError(response_data) from e
            response_data['submission'] = submission

    if params.get('action') in ['previous', 'save_exit', 'next']:
        return response_data, status.SEE_OTHER, {}
    return response_data, status.OK, {}


def _commands(form: CoreMetadataForm, submission: Submission,
              creator: User, client: Client) -> Tuple[List[Event], List[bool]]:
    commands: List[Event] = []
    valid: List[bool] = []

    if form.title.data and submission.metadata \
            and form.title.data != submission.metadata.title:
        command = SetTitle(title=form.title.data, creator=creator,
                           client=client)
        valid.append(validate_command(form, command, submission, 'title'))
        commands.append(command)

    if form.abstract.data and submission.metadata \
            and form.abstract.data != submission.metadata.abstract:
        command = SetAbstract(abstract=form.abstract.data, creator=creator,
                              client=client)
        valid.append(validate_command(form, command, submission, 'abstract'))
        commands.append(command)

    if form.comments.data and submission.metadata \
            and form.comments.data != submission.metadata.comments:
        command = SetComments(comments=form.comments.data, creator=creator,
                              client=client)
        valid.append(validate_command(form, command, submission, 'comments'))
        commands.append(command)

    value = form.authors_display.data
    if value and submission.metadata \
            and value != submission.metadata.authors_display:
        command = SetAuthors(authors_display=form.authors_display.data,
                             creator=creator, client=client)
        valid.append(validate_command(form, command, submission,
                                      'authors_display'))
        commands.append(command)
    return commands, valid


def _opt_commands(form: OptionalMetadataForm, submission: Submission,
                  creator: User, client: Client) \
        -> Tuple[List[Event], List[bool]]:

    commands: List[Event] = []
    valid: List[bool] = []

    if form.msc_class.data and submission.metadata \
            and form.msc_class.data != submission.metadata.msc_class:
        command = SetMSCClassification(msc_class=form.msc_class.data,
                                       creator=creator, client=client)
        valid.append(validate_command(form, command, submission, 'msc_class'))
        commands.append(command)

    if form.acm_class.data and submission.metadata \
            and form.acm_class.data != submission.metadata.acm_class:
        command = SetACMClassification(acm_class=form.acm_class.data,
                                       creator=creator, client=client)
        valid.append(validate_command(form, command, submission, 'acm_class'))
        commands.append(command)

    if form.report_num.data and submission.metadata \
            and form.report_num.data != submission.metadata.report_num:
        command = SetReportNumber(report_num=form.report_num.data,
                                  creator=creator, client=client)
        valid.append(validate_command(form, command, submission, 'report_num'))
        commands.append(command)

    if form.journal_ref.data and submission.metadata \
            and form.journal_ref.data != submission.metadata.journal_ref:
        command = SetJournalReference(journal_ref=form.journal_ref.data,
                                      creator=creator, client=client)
        valid.append(validate_command(form, command, submission,
                                      'journal_ref'))
        commands.append(command)

    if form.doi.data and submission.metadata \
            and form.doi.data != submission.metadata.doi:
        command = SetDOI(doi=form.doi.data, creator=creator, client=client)
        valid.append(validate_command(form, command, submission, 'doi'))
        commands.append(command)
    return commands, valid
