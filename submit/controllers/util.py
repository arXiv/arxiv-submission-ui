"""Helpers for controllers."""

from typing import Callable, Any, Dict, Tuple, Optional, List

from werkzeug import MultiDict
from werkzeug.exceptions import InternalServerError, NotFound, BadRequest
from flask import url_for

from wtforms.widgets import ListWidget, CheckboxInput, Select, HTMLString, \
    html_params
from wtforms import StringField, PasswordField, SelectField, \
    SelectMultipleField, Form, validators
from wtforms.fields.core import UnboundField

from arxiv import status, taxonomy
from arxiv.users.domain import Session
import arxiv.submission as events
from ..domain import SubmissionStage
from ..util import load_submission

Response = Tuple[Dict[str, Any], int, Dict[str, Any]]   # pylint: disable=C0103


class OptGroupSelectWidget(Select):
    """Select widget with optgroups."""

    def __call__(self, field: SelectField, **kwargs: Any) -> HTMLString:
        """Render the `select` element with `optgroup`s."""
        kwargs.setdefault('id', field.id)
        if self.multiple:
            kwargs['multiple'] = True
        html = [f'<select {html_params(name=field.name, **kwargs)}>']
        html.append('<option></option>')
        for group_label, items in field.choices:
            html.append('<optgroup %s>' % html_params(label=group_label))
            for value, label in items:
                option = self.render_option(value, label, value == field.data)
                html.append(option)
            html.append('</optgroup>')
        html.append('</select>')
        return HTMLString(''.join(html))


class OptGroupSelectField(SelectField):
    """A select field with optgroups."""

    widget = OptGroupSelectWidget()

    def pre_validate(self, form: Form) -> None:
        """Don't forget to validate also values from embedded lists."""
        for group_label, items in self.choices:
            for value, label in items:
                if value == self.data:
                    return
        raise ValueError(self.gettext('Not a valid choice'))

    def _value(self) -> str:
        data: str = self.data
        return data


class OptGroupSelectMultipleField(SelectMultipleField):
    """A multiple select field with optgroups."""

    widget = OptGroupSelectWidget(multiple=True)

    # def pre_validate(self, form: Form) -> None:
    #     """Don't forget to validate also values from embedded lists."""
    #     for group_label, items in self.choices:
    #         for value, label in items:
    #             if value == self.data:
    #                 return
    #     raise ValueError(self.gettext('Not a valid choice'))

    def _value(self) -> List[str]:
        data: List[str] = self.data
        return data


class SubmissionMixin:
    """
    Provides submission-related integration for :class:`.Form`s.

    Since the command events in :mod:`events` provide input validation, it
    is convenient to instantiate those :class:`events.Event`s during form
    validation. To do this, however, we need to know about the
    :class:`events.Submission` and the event creator (an
    :class:`events.User`). This mixin provides :prop:`.submission` and
    :prop:`.creator` for that purpose.

    Since we're instantiating the :class:`event.Event`s during form validation,
    we also want to keep those around so that we don't have to create them
    twice. So this mixin also provides :prop:`.events` and :meth:`._add_event`.

    Examples
    --------
    .. code-block:: python

       >>> from wtforms import Form, TextField, validators
       >>> from submit.controllers.util import SubmissionMixin
       >>> import arxiv.submission as events
       >>>
       >>> class FooForm(Form, SubmissionMixin):
       ...     title = TextField('Title')
       ...
       ...     def validate_title(self, field):
       ...         if self.submission.metadata.title == field.data:
       ...             return
       ...         self._validate_event(SetTitle, title=field.data)
       ...
       >>> form = FooForm(data)
       >>> form.submission = submission
       >>> form.creator = submitter
       >>> form.validate()

    """

    def _set_submission(self, submission: events.Submission) -> None:
        self._submission = submission

    def _get_submission(self) -> events.Submission:
        return self._submission

    def _set_creator(self, creator: events.User) -> None:
        self._creator = creator

    def _get_creator(self) -> events.User:
        return self._creator

    submission = property(_get_submission, _set_submission)
    creator = property(_get_creator, _set_creator)

    def _add_event(self, event: events.Event) -> None:
        if not hasattr(self, '_events'):
            self._events = []
        self._events.append(event)

    def _validate_event(self, event_type: type, **data: Any) -> None:
        event = event_type(creator=self.creator, **data)
        self._add_event(event)
        try:
            event.validate(self.submission)
        except events.InvalidEvent as e:
            raise validators.ValidationError(e.message)

    @property
    def events(self) -> List[events.Event]:
        """Command event instances created during form validation."""
        if not hasattr(self, '_events'):
            self._events = []
        return self._events


class FieldMixin:
    """Provide a convenience classmethod for field names."""

    @classmethod
    def fields(cls):
        """Convenience accessor for form field names."""
        return [key for key in dir(cls)
                if isinstance(getattr(cls, key), UnboundField)]


# TODO: currently this does nothing with the client. We will need to add that
# bit once we have a plan for handling client information in this interface.
def user_and_client_from_session(session: Session) \
        -> Tuple[events.User, Optional[events.Client]]:
    """
    Get submission user/client representations from a :class:`.Session`.

    When we're building submission-related events, we frequently need a
    submission-friendly representation of the user or client responsible for
    those events. This function generates those event-domain representations
    from a :class:`arxiv.users.domain.Submission` object.
    """
    user = events.domain.User(
        session.user.user_id,
        email=session.user.email,
        forename=getattr(session.user.name, 'forename', None),
        surname=getattr(session.user.name, 'surname', None),
        suffix=getattr(session.user.name, 'suffix', None),
        endorsements=session.authorizations.endorsements
    )
    return user, None
