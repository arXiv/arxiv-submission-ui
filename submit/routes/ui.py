"""Provides routes for the submission user interface."""

from typing import Optional, Callable, Dict, List

from werkzeug import MultiDict
from werkzeug.exceptions import InternalServerError
from flask import Blueprint, make_response, redirect, request, \
                  render_template, url_for, Response, g
from arxiv import status, taxonomy
from submit import controllers
from arxiv.users import auth
import arxiv.submission as events

from .auth import can_edit_submission
from ..domain import SubmissionStage, Submission, ReplacementStage, Stages
from .util import flow_control, inject_stage
from .. import util

blueprint = Blueprint('ui', __name__, url_prefix='/')
blueprint.context_processor(inject_stage)


@blueprint.route('/', methods=['GET', 'POST'])
@auth.decorators.scoped(auth.scopes.CREATE_SUBMISSION)
def create_submission():
    """Create a new submission."""
    request_data = MultiDict(request.form.items(multi=True))
    data, code, headers = controllers.create.create(
        request.method,
        request_data,
        request.session
    )
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


@blueprint.route('/<int:submission_id>/delete', methods=['GET', 'POST'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION)
def delete_submission(submission_id: int):
    """Delete, or roll a submission back to the last published state."""
    request_data = MultiDict(request.form.items(multi=True))
    data, code, headers = controllers.delete.delete(
        request.method,
        request_data,
        request.session,
        submission_id
    )
    if code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]:
        rendered = render_template(
            "submit/confirm_delete_submission.html",
            pagetitle='Delete submission or replacement',
            **data
        )
        response = make_response(rendered, code)
        return response
    if 'Location' in headers:
        return redirect(headers['Location'], code=code)
    raise InternalServerError('Something went wrong')


@blueprint.route('/<int:submission_id>/replace', methods=['POST'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION)
def create_replacement(submission_id: int):
    """Create a replacement submission."""
    request_data = MultiDict(request.form.items(multi=True))
    data, code, headers = controllers.create.replace(
        request.method,
        request_data,
        request.session,
        submission_id
    )
    if code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]:
        rendered = render_template(
            "submit/replace.html",
            pagetitle='Create a new version (replacement)',
            **data
        )
        response = make_response(rendered, code)
        return response
    if 'Location' in headers:
        return redirect(headers['Location'], code=code)
    raise InternalServerError('Something went wrong')


@blueprint.route('/<int:submission_id>', methods=['GET'])
@auth.decorators.scoped(auth.scopes.VIEW_SUBMISSION,
                        authorizer=can_edit_submission)
def submission_status(submission_id: int) -> Response:
    """Display the current state of the submission."""
    data, code, headers = controllers.submission_status(
        request.session,
        submission_id
    )
    rendered = render_template("submit/status.html",
                               pagetitle='Submission status',
                               **data)
    return make_response(rendered, code)


# TODO: remove me!!
@blueprint.route('/<int:submission_id>/publish', methods=['GET'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=can_edit_submission)
def publish(submission_id: int) -> Response:
    """WARNING WARNING WARNING this is for testing purposes only."""
    util.publish_submission(submission_id)
    target = url_for('ui.submission_status', submission_id=submission_id)
    return Response(response={}, status=status.HTTP_303_SEE_OTHER,
                    headers={'Location': target})


# TODO: remove me!!
@blueprint.route('/<int:submission_id>/place_on_hold', methods=['GET'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=can_edit_submission)
def place_on_hold(submission_id: int) -> Response:
    """WARNING WARNING WARNING this is for testing purposes only."""
    util.place_on_hold(submission_id)
    target = url_for('ui.submission_status', submission_id=submission_id)
    return Response(response={}, status=status.HTTP_303_SEE_OTHER,
                    headers={'Location': target})


# TODO: remove me!!
@blueprint.route('/<int:submission_id>/apply_cross', methods=['GET'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=can_edit_submission)
def apply_cross(submission_id: int) -> Response:
    """WARNING WARNING WARNING this is for testing purposes only."""
    util.apply_cross(submission_id)
    target = url_for('ui.submission_status', submission_id=submission_id)
    return Response(response={}, status=status.HTTP_303_SEE_OTHER,
                    headers={'Location': target})


# TODO: remove me!!
@blueprint.route('/<int:submission_id>/reject_cross', methods=['GET'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=can_edit_submission)
def reject_cross(submission_id: int) -> Response:
    """WARNING WARNING WARNING this is for testing purposes only."""
    util.reject_cross(submission_id)
    target = url_for('ui.submission_status', submission_id=submission_id)
    return Response(response={}, status=status.HTTP_303_SEE_OTHER,
                    headers={'Location': target})


# TODO: remove me!!
@blueprint.route('/<int:submission_id>/apply_withdrawal', methods=['GET'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=can_edit_submission)
def apply_withdrawal(submission_id: int) -> Response:
    """WARNING WARNING WARNING this is for testing purposes only."""
    util.apply_withdrawal(submission_id)
    target = url_for('ui.submission_status', submission_id=submission_id)
    return Response(response={}, status=status.HTTP_303_SEE_OTHER,
                    headers={'Location': target})

# TODO: remove me!!
@blueprint.route('/<int:submission_id>/reject_withdrawal', methods=['GET'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=can_edit_submission)
def reject_withdrawal(submission_id: int) -> Response:
    """WARNING WARNING WARNING this is for testing purposes only."""
    util.reject_withdrawal(submission_id)
    target = url_for('ui.submission_status', submission_id=submission_id)
    return Response(response={}, status=status.HTTP_303_SEE_OTHER,
                    headers={'Location': target})


@blueprint.route('/<int:submission_id>/verify_user',
                 endpoint=Stages.VERIFY_USER.value,
                 methods=['GET', 'POST'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=can_edit_submission)
@flow_control(Stages.VERIFY_USER)
def verify_user(submission_id: Optional[int] = None) -> Response:
    """Render the submit start page."""
    request_data = MultiDict(request.form.items(multi=True))
    data, code, headers = controllers.verify_user.verify_user(
        request.method,
        request_data,
        request.session,
        submission_id
    )
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
                 endpoint=Stages.AUTHORSHIP.value,
                 methods=['GET', 'POST'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=can_edit_submission)
@flow_control(Stages.AUTHORSHIP)
def authorship(submission_id: int) -> Response:
    """Render step 2, authorship."""
    request_data = MultiDict(request.form.items(multi=True))
    data, code, headers = controllers.authorship.authorship(
        request.method,
        request_data,
        request.session,
        submission_id
    )

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
                 endpoint=Stages.LICENSE.value,
                 methods=['GET', 'POST'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=can_edit_submission)
@flow_control(Stages.LICENSE)
def license(submission_id: int) -> Response:
    """Render step 3, select license."""
    request_data = MultiDict(request.form.items(multi=True))
    data, code, headers = controllers.license.license(
        request.method,
        request_data,
        request.session,
        submission_id
    )

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
                 endpoint=Stages.POLICY.value,
                 methods=['GET', 'POST'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=can_edit_submission)
@flow_control(Stages.POLICY)
def policy(submission_id: int) -> Response:
    """Render step 4, policy agreement."""
    request_data = MultiDict(request.form.items(multi=True))
    data, code, headers = controllers.policy.policy(
        request.method,
        request_data,
        request.session,
        submission_id
    )

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
                 endpoint=Stages.CLASSIFICATION.value,
                 methods=['GET', 'POST'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=can_edit_submission)
@flow_control(Stages.CLASSIFICATION)
def classification(submission_id: int) -> Response:
    """Render step 5, choose classification."""
    request_data = MultiDict(request.form.items(multi=True))
    data, code, headers = controllers.classification.classification(
        request.method,
        request_data,
        request.session,
        submission_id
    )
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
                 endpoint=Stages.CROSS_LIST.value,
                 methods=['GET', 'POST'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=can_edit_submission)
@flow_control(Stages.CROSS_LIST)
def cross_list(submission_id: int) -> Response:
    """Render step 6, secondary classes."""
    request_data = MultiDict(request.form.items(multi=True))
    data, code, headers = controllers.classification.cross_list(
        request.method,
        request_data,
        request.session,
        submission_id
    )
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
                 endpoint=Stages.FILE_UPLOAD.value,
                 methods=['GET', 'POST'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=can_edit_submission)
@flow_control(Stages.FILE_UPLOAD)
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
@flow_control(Stages.FILE_UPLOAD)
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
@flow_control(Stages.FILE_UPLOAD)
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
                 endpoint=Stages.FILE_PROCESS.value,
                 methods=['GET'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=can_edit_submission)
@flow_control(Stages.FILE_PROCESS)
def file_process(submission_id: int) -> Response:
    """Render step 8, file processing."""
    code = status.HTTP_200_OK
    rendered = render_template(
        "submit/file_process.html",
        pagetitle='Process Files',
        submission_id=submission_id
    )
    response = make_response(rendered, code)
    return response


@blueprint.route('/<int:submission_id>/add_metadata',
                 endpoint=Stages.ADD_METADATA.value,
                 methods=['GET', 'POST'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=can_edit_submission)
@flow_control(Stages.ADD_METADATA)
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
                 endpoint=Stages.ADD_OPTIONAL_METADATA.value,
                 methods=['GET', 'POST'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=can_edit_submission)
@flow_control(Stages.ADD_OPTIONAL_METADATA)
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
                 endpoint=Stages.FINAL_PREVIEW.value,
                 methods=['GET'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=can_edit_submission)
@flow_control(Stages.FINAL_PREVIEW)
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


# Other workflows.


@blueprint.route('/<int:submission_id>/jref', methods=['GET', 'POST'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=can_edit_submission)
def jref(submission_id: Optional[int] = None) -> Response:
    """Render the JREF submission page."""
    request_data = MultiDict(request.form.items(multi=True))
    data, code, headers = controllers.jref.jref(
        request.method,
        request_data,
        request.session,
        submission_id
    )
    if code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]:
        rendered = render_template("submit/jref.html",
                                   pagetitle='Add journal reference',
                                   **data)
        return make_response(rendered, code)
    return Response(response=data, status=code, headers=headers)


@blueprint.route('/<int:submission_id>/withdraw', methods=['GET', 'POST'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=can_edit_submission)
def withdraw(submission_id: Optional[int] = None) -> Response:
    """Render the withdrawal request page."""
    request_data = MultiDict(request.form.items(multi=True))
    data, code, headers = controllers.withdraw.request_withdrawal(
        request.method,
        request_data,
        request.session,
        submission_id
    )
    if code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]:
        rendered = render_template("submit/withdraw.html",
                                   pagetitle='Request withdrawal',
                                   **data)
        return make_response(rendered, code)
    return Response(response=data, status=code, headers=headers)


@blueprint.route('/<int:submission_id>/request_cross', methods=['GET', 'POST'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=can_edit_submission)
def request_cross(submission_id: Optional[int] = None) -> Response:
    """Render the cross-list request page."""
    request_data = MultiDict(request.form.items(multi=True))
    data, code, headers = controllers.cross.request_cross(
        request.method,
        request_data,
        request.session,
        submission_id
    )
    if code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]:
        rendered = render_template("submit/request_cross_list.html",
                                   pagetitle='Request cross-list',
                                   **data)
        return make_response(rendered, code)
    return Response(response=data, status=code, headers=headers)


def inject_get_next_stage_for_submission() -> Dict[str, Callable]:
    def get_next_stage_for_submission(this_submission: Submission) -> str:
        if this_submission.version == 1:
            stage = SubmissionStage(this_submission)
        else:
            stage = ReplacementStage(this_submission)
        return url_for(f'ui.{stage.next_stage.value}',
                       submission_id=this_submission.submission_id)
    return {'get_next_stage_for_submission': get_next_stage_for_submission}


@blueprint.app_template_filter()
def endorsetype(endorsements: List[str]) -> str:
    """
    Transmit endorsement status to template for message filtering.

    Parameters
    ----------
    endorsements : list
        The list of categories (str IDs) for which the user is endorsed.

    Returns
    -------
    str
        For now.
    """
    if(len(endorsements) == 0):
        return 'None'
    elif(len(taxonomy.CATEGORIES_ACTIVE.keys()) - len(endorsements) == 0):
        return 'All'
    elif(len(taxonomy.CATEGORIES_ACTIVE.keys()) - len(endorsements) > 0):
        return 'Some'
    else:
        return 'Error'
