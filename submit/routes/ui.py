"""Provides routes for the submission user interface."""

from typing import Optional
from werkzeug import MultiDict
from werkzeug.exceptions import InternalServerError
from flask import Blueprint, make_response, redirect, request, \
                  render_template, url_for, Response
from arxiv import status
from submit import controllers
from arxiv.users import auth
import arxiv.submission as events

from .auth import can_edit_submission
from ..domain import SubmissionStage
from ..util import flow_control

blueprint = Blueprint('ui', __name__, url_prefix='/')


@blueprint.route('/user')
def user() -> Response:
    """Give save and exit button a place to go."""
    return redirect('https://www.arxiv.org/user')


@blueprint.route('/progress', methods=['GET'])
def test_page() -> Response:
    """Render a page to test progress bar display."""
    rendered = render_template("submit/progress.html", pagetitle='Progress bar')
    response = make_response(rendered, status.HTTP_200_OK)
    return response


@blueprint.route('/error', methods=['GET'])
def error_page() -> Response:
    """Render a page to test progress bar display."""
    rendered = render_template("submit/error_messages.html",
                               pagetitle='Help and Errors')
    response = make_response(rendered, status.HTTP_200_OK)
    return response


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


@blueprint.route('/<int:submission_id>/verify_user',
                 endpoint=SubmissionStage.VERIFY_USER, methods=['GET', 'POST'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=can_edit_submission)
@flow_control(SubmissionStage.VERIFY_USER)
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
    return Response(response=data, status=code, headers=headers)


@blueprint.route('/<int:submission_id>/authorship',
                 endpoint=SubmissionStage.AUTHORSHIP, methods=['GET', 'POST'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=can_edit_submission)
@flow_control(SubmissionStage.AUTHORSHIP)
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
    return Response(response=data, status=code, headers=headers)


@blueprint.route('/<int:submission_id>/license',
                 endpoint=SubmissionStage.LICENSE, methods=['GET', 'POST'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=can_edit_submission)
@flow_control(SubmissionStage.LICENSE)
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
    return Response(response=data, status=code, headers=headers)


@blueprint.route('/<int:submission_id>/policy',
                 endpoint=SubmissionStage.POLICY, methods=['GET', 'POST'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=can_edit_submission)
@flow_control(SubmissionStage.POLICY)
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
    return Response(response=data, status=code, headers=headers)


@blueprint.route('/<int:submission_id>/classification',
                 endpoint=SubmissionStage.CLASSIFICATION,
                 methods=['GET', 'POST'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=can_edit_submission)
@flow_control(SubmissionStage.CLASSIFICATION)
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
    return Response(response=data, status=code, headers=headers)


@blueprint.route('/<int:submission_id>/cross_list',
                 endpoint=SubmissionStage.CROSS_LIST,
                 methods=['GET', 'POST'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=can_edit_submission)
@flow_control(SubmissionStage.CROSS_LIST)
def cross_list(submission_id: int) -> Response:
    """Render step 6, secondary classes."""
    request_data = MultiDict(request.form.items(multi=True))
    data, code, headers = controllers.cross_list(request.method, request_data,
                                                 request.session,
                                                 submission_id)
    if code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]:
        rendered = render_template(
            "submit/cross_list.html",
            pagetitle='Choose Cross-List Classifications',
            **data
        )
        response = make_response(rendered, code)
        return response
    return Response(response=data, status=code, headers=headers)


@blueprint.route('/<int:submission_id>/file_upload',
                 endpoint=SubmissionStage.FILE_UPLOAD, methods=['GET', 'POST'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=can_edit_submission)
@flow_control(SubmissionStage.FILE_UPLOAD)
def file_upload(submission_id: int) -> Response:
    """Render step 7, file upload."""
    request_data = MultiDict(request.form.items(multi=True))
    data, code, headers = controllers.upload_files(
        request.method,
        request_data,
        request.files,
        request.session,
        submission_id,
        request.environ['token']
    )
    if code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]:
        rendered = render_template("submit/file_upload.html",
                                   pagetitle='Upload Files', **data)
        return make_response(rendered, code)
    return Response(response=data, status=code, headers=headers)


@blueprint.route('/<int:submission_id>/file_delete', methods=['GET', 'POST'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=can_edit_submission)
@flow_control(SubmissionStage.FILE_UPLOAD)
def file_delete(submission_id: int) -> Response:
    """Provide the file deletion endpoint, part of the upload step."""
    if request.method == 'GET':
        request_data = MultiDict(request.args.items(multi=True))
    elif request.method == 'POST':
        request_data = MultiDict(request.form.items(multi=True))
    data, code, headers = controllers.delete_file(
        request.method,
        request_data,
        request.session,
        submission_id,
        request.environ['token']
    )
    if code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]:
        rendered = render_template("submit/confirm_delete.html",
                                   pagetitle='Delete File', **data)
        response = make_response(rendered, code)
        return response
    return Response(response=data, status=code, headers=headers)


@blueprint.route('/<int:submission_id>/file_delete_all',
                 methods=['GET', 'POST'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=can_edit_submission)
@flow_control(SubmissionStage.FILE_UPLOAD)
def file_delete_all(submission_id: int) -> Response:
    """Provide endpoint to delete all files, part of the upload step."""
    if request.method == 'GET':
        request_data = MultiDict(request.args.items(multi=True))
    elif request.method == 'POST':
        request_data = MultiDict(request.form.items(multi=True))
    data, code, headers = controllers.delete_all_files(
        request.method,
        request_data,
        request.session,
        submission_id,
        request.environ['token']
    )
    if code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]:
        rendered = render_template("submit/confirm_delete_all.html",
                                   pagetitle='Delete All Files', **data)
        response = make_response(rendered, code)
        return response
    return Response(response=data, status=code, headers=headers)


@blueprint.route('/<int:submission_id>/file_process',
                 endpoint=SubmissionStage.FILE_PROCESS, methods=['GET'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=can_edit_submission)
@flow_control(SubmissionStage.FILE_PROCESS)
def file_process(submission_id: int) -> Response:
    """Render step 8, file processing."""
    code = status.HTTP_200_OK
    rendered = render_template(
        "submit/file_process.html",
        pagetitle='Process Files'
    )
    response = make_response(rendered, code)
    return response


@blueprint.route('/<int:submission_id>/add_metadata',
                 endpoint=SubmissionStage.ADD_METADATA,
                 methods=['GET', 'POST'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=can_edit_submission)
@flow_control(SubmissionStage.ADD_METADATA)
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
        return response
    return Response(response=data, status=code, headers=headers)


@blueprint.route('/<int:submission_id>/add_optional_metadata',
                 endpoint=SubmissionStage.ADD_OPTIONAL_METADATA,
                 methods=['GET', 'POST'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=can_edit_submission)
@flow_control(SubmissionStage.ADD_OPTIONAL_METADATA)
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
        return response
    return Response(response=data, status=code, headers=headers)


@blueprint.route('/<int:submission_id>/final_preview',
                 endpoint=SubmissionStage.FINAL_PREVIEW, methods=['GET'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=can_edit_submission)
@flow_control(SubmissionStage.FINAL_PREVIEW)
def final_preview(submission_id: int) -> Response:
    """Render step 10, preview."""
    rendered = render_template(
        "submit/final_preview.html",
        pagetitle='Preview and Approve'
    )
    code = status.HTTP_200_OK
    response = make_response(rendered, code)
    return response


# TODO: I'm not sure that we need these? -E

@blueprint.route('/<int:submission_id>/confirm_submit', methods=['GET'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=can_edit_submission)
def confirm_submit(submission_id: int) -> Response:
    """Render the final confirmation page."""
    rendered = render_template(
        "submit/confirm_submit.html",
        pagetitle='Submission Confirmed'
    )
    code = status.HTTP_200_OK
    response = make_response(rendered, code)
    return response


@blueprint.route('/<int:submission_id>/confirm_delete', methods=['GET'])
def confirm_delete(submission_id: int) -> Response:
    """Confirm user initiated file deletion."""
    rendered = render_template(
        "submit/confirm_delete.html",
        pagetitle='Delete Files'
    )
    code = status.HTTP_200_OK
    response = make_response(rendered, code)
    return response
