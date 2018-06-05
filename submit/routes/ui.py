"""Provides routes for the submission user interface."""

from flask import (Blueprint, make_response, redirect, request,
                   render_template, url_for)
from arxiv import status
import submit.controllers as controllers

blueprint = Blueprint('ui', __name__, url_prefix='/')

# TODO: might be refactored into a series of macros and fewer single-page
# templates, initial setup is for testing purposes and to get started.


@blueprint.route('/create', methods=['GET', 'POST'])
@blueprint.route('/<int:submission_id>/verify_user', methods=['GET', 'POST'])
def verify_user(submission_id=None):
    """Render the submit start page. Foreshortened validation for testing."""
    response, code, headers = controllers.verify_user(request.args, submission_id)

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


@blueprint.route('authorship', methods=['GET'])
def authorship():
    """Render step 2, authorship. Foreshortened validation for testing."""
    rendered = render_template(
        "submit/authorship.html",
        pagetitle='Confirm Authorship'
    )
    response = make_response(rendered, status.HTTP_200_OK)
    return response


@blueprint.route('license', methods=['GET'])
def license():
    """Render step 3, select license. Foreshortened validation for testing."""
    rendered = render_template(
        "submit/license.html",
        pagetitle='Select a License'
    )
    response = make_response(rendered, status.HTTP_200_OK)
    return response


@blueprint.route('policy_ack', methods=['GET'])
def policy_ack():
    """Render step 4, policy agreement."""
    rendered = render_template(
        "submit/policy.html",
        pagetitle='Acknowledge Policy Statement'
    )
    response = make_response(rendered, status.HTTP_200_OK)
    return response


@blueprint.route('classification', methods=['GET'])
def classification():
    """Render step 5, choose classification."""
    rendered = render_template(
        "submit/classification.html",
        pagetitle='Choose a Primary Classification'
    )
    response = make_response(rendered, status.HTTP_200_OK)
    return response


@blueprint.route('cross', methods=['GET'])
def secondary_class():
    """Render step 6, secondary classes."""
    rendered = render_template(
        "submit/secondary_class.html",
        pagetitle='Choose Secondary Classifications'
    )
    response = make_response(rendered, status.HTTP_200_OK)
    return response


@blueprint.route('file_upload', methods=['GET'])
def file_upload():
    """Render step 7, file add or edit."""
    rendered = render_template(
        "submit/file_upload.html",
        pagetitle='Add or Edit Files'
    )
    response = make_response(rendered, status.HTTP_200_OK)
    return response


@blueprint.route('file_process', methods=['GET'])
def file_process():
    """Render step 8, file processing."""
    rendered = render_template(
        "submit/file_process.html",
        pagetitle='Process Files'
    )
    response = make_response(rendered, status.HTTP_200_OK)
    return response


@blueprint.route('add_metadata', methods=['GET'])
def add_metadata():
    """Render step 9, metadata."""
    rendered = render_template(
        "submit/add_metadata.html",
        pagetitle='Add or Edit Metadata'
        )
    response = make_response(rendered, status.HTTP_200_OK)
    return response


@blueprint.route('add_optional_metadata', methods=['GET'])
def add_optional_metadata():
    """Render step 9, metadata."""
    rendered = render_template(
        "submit/add_optional_metadata.html",
        pagetitle='Add or Edit Metadata'
        )
    response = make_response(rendered, status.HTTP_200_OK)
    return response


@blueprint.route('final_preview', methods=['GET'])
def final_preview():
    """Render step 10, preview."""
    rendered = render_template(
        "submit/final_preview.html",
        pagetitle='Preview and Approve'
    )
    response = make_response(rendered, status.HTTP_200_OK)
    return response


@blueprint.route('confirm_submit', methods=['GET'])
def confirm_submit():
    """Render the final confirmation page."""
    rendered = render_template(
        "submit/confirm_submit.html",
        pagetitle='Submission Confirmed'
    )
    response = make_response(rendered, status.HTTP_200_OK)
    return response
