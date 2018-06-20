"""Provides a controller for updating metadata on a submission."""

from typing import Tuple, Dict, Any

from werkzeug import MultiDict
from werkzeug.exceptions import InternalServerError
from flask import url_for
from wtforms import Form
from wtforms.fields import TextField, TextAreaField, Field
from wtforms.fields.core import UnboundField
from wtforms import validators

from arxiv import status
from arxiv.base import logging
import events

from .util import flow_control, load_submission

# from arxiv-submission-core.events.event import VerifyContactInformation

logger = logging.getLogger(__name__)  # pylint: disable=C0103

Response = Tuple[Dict[str, Any], int, Dict[str, Any]]  # pylint: disable=C0103


class FieldMixin:
    """Provide a convenience classmethod for field names."""

    @classmethod
    def fields(cls):
        """Convenience accessor for form field names."""
        return [key for key in dir(cls)
                if isinstance(getattr(cls, key), UnboundField)]


class CoreMetadataForm(Form, FieldMixin):
    """Handles core metadata fields on a submission."""

    title = TextField('Title', validators=[validators.Length(min=6, max=255)])
    authors_display = TextField(
        'Authors',
        validators=[validators.Length(min=6)],
        description=(
            "use <code>Forename Surname</code> or <code>I. "
            "Surname</code>; separate individual authors with "
            "a comma or 'and'."
        )
    )
    abstract = TextAreaField('Abstract',
                             validators=[validators.Length(min=6, max=1920)],
                             description='Limit of 1920 characters')
    comments = TextField('Comments',
                         validators=[validators.optional()],
                         description=(
                            "Supplemental information such as number of pages "
                            "or figures, conference information."
                         ))


class OptionalMetadataForm(Form, FieldMixin):
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


def _data_from_submission(params: MultiDict, submission: events.Submission,
                          form_class: type) -> MultiDict:
    if not submission.metadata:
        return params
    for field in form_class.fields():
        params[field] = getattr(submission.metadata, field, '')
    return params


def _get_fields_to_update(form: CoreMetadataForm,
                          submission: events.Submission) -> dict:
    """
    Determine which fields to update on the submission.

    There is nothing to do if a value has not changed.
    """
    to_update = {}
    for field in form.fields():
        form_value = getattr(getattr(form, field), 'data', '')
        if form_value != getattr(submission.metadata, field):
            to_update[field] = form_value
    return to_update


@flow_control('ui.file_process', 'ui.add_optional_metadata', 'ui.user')
def metadata(method: str, params: MultiDict, submission_id: int) -> Response:
    """Update metadata on the submission."""
    logger.debug(f'method: {method}, submission: {submission_id}. {params}')

    # TODO: Create a concrete User from cookie info.
    submitter = events.domain.User(1, email='ian413@cornell.edu',
                                   forename='Ima', surname='Nauthor')

    # Will raise NotFound if there is no such submission.
    submission = load_submission(submission_id)
    # The form should be prepopulated based on the current state of the
    # submission.
    if method == 'GET':
        params = _data_from_submission(params, submission, CoreMetadataForm)

    form = CoreMetadataForm(params)
    response_data = {'submission_id': submission_id, 'form': form}

    if method == 'POST':
        if not form.validate():
            logger.debug('Invalid form data; return bad request')
            return response_data, status.HTTP_400_BAD_REQUEST, {}

        logger.debug('Form is valid, with data: %s', str(form.data))

        # We only want to apply an UpdateMetadata if the metadata has
        # actually changed.
        to_update = _get_fields_to_update(form, submission)
        if to_update:   # Metadata has changed.
            try:
                # Create UpdateMetadata event
                submission, stack = events.save(  # pylint: disable=W0612
                    events.UpdateMetadata(
                        creator=submitter,
                        metadata=list(to_update.items())
                    ),
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


@flow_control('ui.add_metadata', 'ui.confirm_submit', 'ui.user')
def optional(method: str, params: MultiDict, submission_id: int) -> Response:
    """Update optional metadata on the submission."""
    logger.debug(f'method: {method}, submission: {submission_id}. {params}')

    # TODO: Create a concrete User from cookie info.
    submitter = events.domain.User(1, email='ian413@cornell.edu',
                                   forename='Ima', surname='Nauthor')

    # Will raise NotFound if there is no such submission.
    submission = load_submission(submission_id)
    # The form should be prepopulated based on the current state of the
    # submission.
    if method == 'GET':
        params = _data_from_submission(params, submission,
                                       OptionalMetadataForm)

    form = OptionalMetadataForm(params)
    response_data = {'submission_id': submission_id, 'form': form}

    if method == 'POST':
        if not form.validate():
            logger.debug('Invalid form data; return bad request')
            return response_data, status.HTTP_400_BAD_REQUEST, {}

        logger.debug('Form is valid, with data: %s', str(form.data))

        # We only want to apply an UpdateMetadata if the metadata has
        # actually changed.
        to_update = _get_fields_to_update(form, submission)
        if to_update:   # Metadata has changed.
            try:
                # Create UpdateMetadata event
                submission, stack = events.save(  # pylint: disable=W0612
                    events.UpdateMetadata(
                        creator=submitter,
                        metadata=list(to_update.items())
                    ),
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
