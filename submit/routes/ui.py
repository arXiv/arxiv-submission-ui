"""Provides routes for the submission user interface."""

from typing import Optional
from werkzeug import MultiDict
from werkzeug.exceptions import InternalServerError
from flask import Blueprint, make_response, redirect, request, \
                  render_template, url_for, Response
from arxiv import status
from submit import controllers
from arxiv.users import auth
from .auth import can_edit_submission
import arxiv.submission as events

blueprint = Blueprint('ui', __name__, url_prefix='/')


@blueprint.route('/user')
def user() -> Response:
    """Give save and exit button a place to go."""
    return redirect('https://www.arxiv.org/user')


@blueprint.route('/', methods=['GET', 'POST'])
@auth.decorators.scoped(auth.scopes.CREATE_SUBMISSION)
def create_submission():
    """Create a new submission."""
    request_data = MultiDict(request.form.items(multi=True))
    data, code, headers = controllers.create(request.method, request_data,
                                             request.session)
    if code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]:
        rendered = render_template(
            "submit/create.html",
            pagetitle='Create a new submission',
            **data
        )
        response = make_response(rendered, code)
        return response
    if 'Location' in headers:
        return redirect(headers['Location'], code=code)
    raise InternalServerError('Something went wrong')


@blueprint.route('/<int:submission_id>/verify_user', methods=['GET', 'POST'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, can_edit_submission)
def verify_user(submission_id: Optional[int] = None) -> Response:
    """Render the submit start page."""
    request_data = MultiDict(request.form.items(multi=True))
    data, code, headers = controllers.verify_user(request.method, request_data,
                                                  request.session,
                                                  submission_id)
    if code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]:
        rendered = render_template(
            "submit/verify_user.html",
            pagetitle='Verify User Information',
            **data
        )
        response = make_response(rendered, code)
        return response
    elif code == status.HTTP_303_SEE_OTHER:
        return redirect(headers['Location'], code=code)


@blueprint.route('/<int:submission_id>/authorship', methods=['GET', 'POST'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, can_edit_submission)
def authorship(submission_id: int) -> Response:
    """Render step 2, authorship."""
    request_data = MultiDict(request.form.items(multi=True))
    data, code, headers = controllers.authorship(request.method, request_data,
                                                 request.session,
                                                 submission_id)

    if code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]:
        rendered = render_template(
            "submit/authorship.html",
            pagetitle='Confirm Authorship',
            **data
        )
        response = make_response(rendered, code)
        return response
    elif code == status.HTTP_303_SEE_OTHER:
        return redirect(headers['Location'], code=code)


@blueprint.route('/<int:submission_id>/license', methods=['GET', 'POST'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, can_edit_submission)
def license(submission_id: int) -> Response:
    """Render step 3, select license."""
    request_data = MultiDict(request.form.items(multi=True))
    data, code, headers = controllers.license(request.method, request_data,
                                              request.session,
                                              submission_id)

    if code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]:
        rendered = render_template(
            "submit/license.html",
            pagetitle='Select a License',
            **data
        )
        response = make_response(rendered, code)
        return response
    elif code == status.HTTP_303_SEE_OTHER:
        return redirect(headers['Location'], code=code)


@blueprint.route('/<int:submission_id>/policy', methods=['GET', 'POST'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, can_edit_submission)
def policy(submission_id: int) -> Response:
    """Render step 4, policy agreement."""
    request_data = MultiDict(request.form.items(multi=True))
    data, code, headers = controllers.policy(request.method, request_data,
                                             request.session,
                                             submission_id)

    if code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]:
        rendered = render_template(
            "submit/policy.html",
            pagetitle='Acknowledge Policy Statement',
            **data
        )
        response = make_response(rendered, code)
        return response
    elif code == status.HTTP_303_SEE_OTHER:
        return redirect(headers['Location'], code=code)


@blueprint.route('/<int:submission_id>/classification',
                 methods=['GET', 'POST'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, can_edit_submission)
def classification(submission_id: int) -> Response:
    """Render step 5, choose classification."""
    request_data = MultiDict(request.form.items(multi=True))
    data, code, headers = controllers.classification(request.method,
                                                     request_data,
                                                     request.session,
                                                     submission_id)
    if code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]:
        rendered = render_template(
            "submit/classification.html",
            pagetitle='Choose a Primary Classification',
            **data
        )
        response = make_response(rendered, code)
        return response
    elif code == status.HTTP_303_SEE_OTHER:
        return redirect(headers['Location'], code=code)


@blueprint.route('/<int:submission_id>/cross_list', methods=['GET', 'POST'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, can_edit_submission)
def cross_list(submission_id: int) -> Response:
    """Render step 6, secondary classes."""
    request_data = MultiDict(request.form.items(multi=True))
    data, code, headers = controllers.cross_list(request.method, request_data,
                                                 request.session,
                                                 submission_id)
    if code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]:
        rendered = render_template(
            "submit/cross_list.html",
            pagetitle='Choose Secondary Classifications',
            **data
        )
        response = make_response(rendered, code)
    elif code == status.HTTP_303_SEE_OTHER:
        return redirect(headers['Location'], code=code)
    return response


@blueprint.route('/<int:submission_id>/file_upload', methods=['GET'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, can_edit_submission)
def file_upload(submission_id: int) -> Response:
    """Render step 7, file add or edit."""
    code = status.HTTP_200_OK
    rendered = render_template(
        "submit/file_upload.html",
        pagetitle='Add or Edit Files'
    )
    response = make_response(rendered, code)
    return response


@blueprint.route('/<int:submission_id>/file_process', methods=['GET'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, can_edit_submission)
def file_process(submission_id: int) -> Response:
    """Render step 8, file processing."""
    code = status.HTTP_200_OK
    rendered = render_template(
        "submit/file_process.html",
        pagetitle='Process Files'
    )
    response = make_response(rendered, code)
    return response


@blueprint.route('/<int:submission_id>/add_metadata', methods=['GET', 'POST'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, can_edit_submission)
def add_metadata(submission_id: int) -> Response:
    """Render step 9, metadata."""
    request_data = MultiDict(request.form.items(multi=True))
    data, code, headers = controllers.metadata(request.method, request_data,
                                               request.session,
                                               submission_id)
    if code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]:
        rendered = render_template(
            "submit/add_metadata.html",
            pagetitle='Add or Edit Metadata',
            **data
        )
        response = make_response(rendered, code)
    elif code == status.HTTP_303_SEE_OTHER:
        return redirect(headers['Location'], code=code)
    return response


@blueprint.route('/<int:submission_id>/add_optional_metadata',
                 methods=['GET', 'POST'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, can_edit_submission)
def add_optional_metadata(submission_id: int) -> Response:
    """Render step 9, metadata."""
    request_data = MultiDict(request.form.items(multi=True))
    data, code, headers = controllers.optional(request.method, request_data,
                                               request.session,
                                               submission_id)
    if code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]:
        rendered = render_template(
            "submit/add_optional_metadata.html",
            pagetitle='Add or Edit Metadata',
            **data
            )
        response = make_response(rendered, code)
    elif code == status.HTTP_303_SEE_OTHER:
        response = redirect(headers['Location'], code=code)
    return response


@blueprint.route('/<int:submission_id>/final_preview', methods=['GET'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, can_edit_submission)
def final_preview(submission_id: int) -> Response:
    """Render step 10, preview."""
    rendered = render_template(
        "submit/final_preview.html",
        pagetitle='Preview and Approve'
    )
    code = status.HTTP_200_OK
    response = make_response(rendered, code)
    return response


@blueprint.route('/<int:submission_id>/confirm_submit', methods=['GET'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, can_edit_submission)
def confirm_submit(submission_id: int) -> Response:
    """Render the final confirmation page."""
    rendered = render_template(
        "submit/confirm_submit.html",
        pagetitle='Submission Confirmed'
    )
    code = status.HTTP_200_OK
    response = make_response(rendered, code)
    return response
