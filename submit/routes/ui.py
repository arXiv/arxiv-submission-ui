"""Provides routes for the submission user interface."""

from typing import Optional
from werkzeug import MultiDict
from flask import Blueprint, make_response, redirect, request, \
                  render_template, url_for, Response
from arxiv import status
from submit import controllers

blueprint = Blueprint('ui', __name__, url_prefix='/')

# TODO: might be refactored into a series of macros and fewer single-page
# templates, initial setup is for testing purposes and to get started.


@blueprint.route('/user')
def user() -> Response:
    """Give save and exit button a place to go."""
    return redirect('https://www.arxiv.org/user')


@blueprint.route('/create', methods=['GET', 'POST'])
@blueprint.route('/<int:submission_id>/verify_user', methods=['GET', 'POST'])
def verify_user(submission_id: Optional[int] = None) -> Response:
    """Render the submit start page."""
    request_data = MultiDict(request.form.items(multi=True))
    data, code, headers = controllers.verify_user(request.method, request_data,
                                                  submission_id)
    if code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]:
        print(data)
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
def authorship(submission_id: int) -> Response:
    """Render step 2, authorship."""
    request_data = MultiDict(request.form.items(multi=True))
    data, code, headers = controllers.authorship(request.method, request_data,
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
def license(submission_id: int) -> Response:
    """Render step 3, select license."""
    request_data = MultiDict(request.form.items(multi=True))
    data, code, headers = controllers.license(request.method, request_data,
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
def policy(submission_id: int) -> Response:
    """Render step 4, policy agreement."""
    request_data = MultiDict(request.form.items(multi=True))
    data, code, headers = controllers.policy(request.method, request_data,
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
def classification(submission_id: int) -> Response:
    """Render step 5, choose classification."""
    request_data = MultiDict(request.form.items(multi=True))
    data, code, headers = controllers.classification(request.method,
                                                     request_data,
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
def cross_list(submission_id: int) -> Response:
    """Render step 6, secondary classes."""
    request_data = MultiDict(request.form.items(multi=True))
    data, code, headers = controllers.cross_list(request.method, request_data,
                                                 submission_id)
    if code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]:
        rendered = render_template(
            "submit/cross_list.html",
            pagetitle='Choose Cross-List Classifications',
            **data
        )
        response = make_response(rendered, code)
    elif code == status.HTTP_303_SEE_OTHER:
        return redirect(headers['Location'], code=code)
    return response


@blueprint.route('/<int:submission_id>/file_upload', methods=['GET'])
def file_upload(submission_id: int) -> Response:
    """Render step 7, file upload."""
    code = status.HTTP_200_OK
    rendered = render_template(
        "submit/file_upload.html",
        pagetitle='Upload Files'
    )
    response = make_response(rendered, code)
    return response


@blueprint.route('/<int:submission_id>/file_process', methods=['GET'])
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
def add_metadata(submission_id: int) -> Response:
    """Render step 9, metadata."""
    request_data = MultiDict(request.form.items(multi=True))
    data, code, headers = controllers.metadata(request.method, request_data,
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
def add_optional_metadata(submission_id: int) -> Response:
    """Render step 9, metadata."""
    request_data = MultiDict(request.form.items(multi=True))
    data, code, headers = controllers.optional(request.method, request_data,
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
def confirm_submit(submission_id: int) -> Response:
    """Render the final confirmation page."""
    rendered = render_template(
        "submit/confirm_submit.html",
        pagetitle='Submission Confirmed'
    )
    code = status.HTTP_200_OK
    response = make_response(rendered, code)
    return response
