"""Provides routes for the submission user interface."""

from flask import (Blueprint, make_response, redirect, request,
                   render_template, url_for)
from arxiv import status
from submit import controllers

blueprint = Blueprint('ui', __name__, url_prefix='/')

# TODO: might be refactored into a series of macros and fewer single-page
# templates, initial setup is for testing purposes and to get started.


@blueprint.route('/user')
def user():
    """Give save and exit button a place to go."""
    return redirect('https://www.arxiv.org/user')


@blueprint.route('/create', methods=['GET', 'POST'])
@blueprint.route('/<int:submission_id>/verify_user', methods=['GET', 'POST'])
def verify_user(submission_id=None):
    """Render the submit start page. Foreshortened validation for testing."""
    response, code, headers = controllers.verify_user(request.args, submission_id)
    print(response, code, headers)
    if code == status.HTTP_200_OK:
        rendered = render_template(
            "submit/verify_user.html",
            pagetitle='Verify User Information',
            **response
        )
        response = make_response(rendered, status.HTTP_200_OK)
        return response
    elif code == status.HTTP_303_SEE_OTHER:
        return redirect(headers['Location'], code=code)


@blueprint.route('/<int:submission_id>/authorship', methods=['GET', 'POST'])
def authorship(submission_id):
    """Render step 2, authorship. Foreshortened validation for testing."""
    response, code, headers = controllers.authorship(request.args, submission_id)

    if code == status.HTTP_200_OK:
        rendered = render_template(
            "submit/authorship.html",
            pagetitle='Confirm Authorship',
            **response
        )
        response = make_response(rendered, status.HTTP_200_OK)
        return response
    elif code == status.HTTP_303_SEE_OTHER:
        return redirect(headers['Location'], code=code)


@blueprint.route('/<int:submission_id>/license', methods=['GET', 'POST'])
def license(submission_id):
    """Render step 3, select license. Foreshortened validation for testing."""
    rendered = render_template(
        "submit/license.html",
        pagetitle='Select a License'
    )
    response = make_response(rendered, status.HTTP_200_OK)
    return response


@blueprint.route('/<int:submission_id>/policy', methods=['GET'])
def policy(submission_id):
    """Render step 4, policy agreement."""
    response, code, headers = controllers.policy(request.args, submission_id)

    if code == status.HTTP_200_OK:
        rendered = render_template(
            "submit/policy.html",
            pagetitle='Acknowledge Policy Statement',
            **response
        )
        response = make_response(rendered, status.HTTP_200_OK)
        return response
    elif code == status.HTTP_303_SEE_OTHER:
        return redirect(headers['Location'], code=code)


@blueprint.route('/<int:submission_id>/classification', methods=['GET'])
def classification(submission_id):
    """Render step 5, choose classification."""
    rendered = render_template(
        "submit/classification.html",
        pagetitle='Choose a Primary Classification'
    )
    response = make_response(rendered, status.HTTP_200_OK)
    return response


@blueprint.route('/<int:submission_id>/crosslist', methods=['GET'])
def crosslist(submission_id):
    """Render step 6, secondary classes."""
    rendered = render_template(
        "submit/secondary_class.html",
        pagetitle='Choose Secondary Classifications'
    )
    response = make_response(rendered, status.HTTP_200_OK)
    return response


@blueprint.route('/<int:submission_id>/file_upload', methods=['GET'])
def file_upload(submission_id):
    """Render step 7, file add or edit."""
    rendered = render_template(
        "submit/file_upload.html",
        pagetitle='Add or Edit Files'
    )
    response = make_response(rendered, status.HTTP_200_OK)
    return response


@blueprint.route('/<int:submission_id>/file_process', methods=['GET'])
def file_process(submission_id):
    """Render step 8, file processing."""
    rendered = render_template(
        "submit/file_process.html",
        pagetitle='Process Files'
    )
    response = make_response(rendered, status.HTTP_200_OK)
    return response


@blueprint.route('/<int:submission_id>/add_metadata', methods=['GET'])
def add_metadata(submission_id):
    """Render step 9, metadata."""
    rendered = render_template(
        "submit/add_metadata.html",
        pagetitle='Add or Edit Metadata'
        )
    response = make_response(rendered, status.HTTP_200_OK)
    return response


@blueprint.route('/<int:submission_id>/add_optional_metadata', methods=['GET'])
def add_optional_metadata(submission_id):
    """Render step 9, metadata."""
    rendered = render_template(
        "submit/add_optional_metadata.html",
        pagetitle='Add or Edit Metadata'
        )
    response = make_response(rendered, status.HTTP_200_OK)
    return response


@blueprint.route('/<int:submission_id>/final_preview', methods=['GET'])
def final_preview(submission_id):
    """Render step 10, preview."""
    rendered = render_template(
        "submit/final_preview.html",
        pagetitle='Preview and Approve'
    )
    response = make_response(rendered, status.HTTP_200_OK)
    return response


@blueprint.route('/<int:submission_id>/confirm_submit', methods=['GET'])
def confirm_submit(submission_id):
    """Render the final confirmation page."""
    rendered = render_template(
        "submit/confirm_submit.html",
        pagetitle='Submission Confirmed'
    )
    response = make_response(rendered, status.HTTP_200_OK)
    return response
