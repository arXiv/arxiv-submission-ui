"""Helpers for controllers."""

from typing import Callable, Any, Dict, Tuple, Optional
from werkzeug import MultiDict
from werkzeug.exceptions import InternalServerError, NotFound
from flask import url_for
from wtforms.widgets import ListWidget, CheckboxInput, Select, HTMLString, \
    html_params
from wtforms import StringField, PasswordField, SelectField, \
    SelectMultipleField, Form
from arxiv import status
import events

Response = Tuple[Dict[str, Any], int, Dict[str, Any]]  # pylint: disable=C0103


# TODO: handle case that there is no prev/next page!
# TODO: handle case that prev/next page doesn't exist.
def flow_control(prev_page: str, next_page: str, exit_page: str) -> Callable:
    """Get a decorator that handles redirection to next/previous steps."""
    def deco(func: Callable) -> Callable:
        """Decorator that applies next/previous redirection."""
        def wrapper(method: str, params: MultiDict, *args: Any,
                    **kwargs: Dict) -> Response:
            """Update the redirect to the next, previous, or exit page."""
            data, status_code, headers = func(method, params, *args, **kwargs)
            # No redirect; nothing to do.
            if status_code != status.HTTP_303_SEE_OTHER:
                return data, status_code, headers

            action = params.get('action')
            if not action and 'Location' not in headers:
                raise InternalServerError('Attempted redirect without URL')

            # Get the submission ID from the response, since it may not have
            # been a param for the controller.
            submission_id = data.get('submission_id')

            def _get_target(page: str) -> str:
                if submission_id:
                    url: str = url_for(page, submission_id=submission_id)
                else:
                    url = url_for(page)
                return url

            if action == 'next':
                headers.update({'Location': _get_target(next_page)})
            elif action == 'previous':
                headers.update({'Location': _get_target(prev_page)})
            elif action == 'save_exit':
                headers.update({'Location': _get_target(exit_page)})
            return data, status_code, headers
        return wrapper
    return deco


def load_submission(submission_id: int) -> events.domain.Submission:
    """
    Load a submission by ID.

    Parameters
    ----------
    submission_id : int

    Returns
    -------
    :class:`events.domain.Submission`

    Raises
    ------
    :class:`werkzeug.exceptions.NotFound`
        Raised when there is no submission with the specified ID.

    """
    try:
        submission, _ = events.load(submission_id)
    except events.exceptions.NoSuchSubmission as e:
        raise NotFound('No such submission.') from e
    return submission


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
