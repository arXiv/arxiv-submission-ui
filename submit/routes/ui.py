"""Provides routes for the submission user interface."""

from typing import Optional, Callable, Dict, List

from werkzeug import MultiDict
from werkzeug.exceptions import InternalServerError
from flask import Blueprint, make_response, redirect, request, \
                  render_template, url_for, Response, g, send_file
from arxiv import status, taxonomy
from submit import controllers
from arxiv.users import auth
import arxiv.submission as events

from .auth import is_owner
from ..domain import SubmissionStage, Submission, ReplacementStage, Stages
from .util import flow_control, inject_stage
from .. import util

ui = Blueprint('ui', __name__, url_prefix='/')
ui.context_processor(inject_stage)

GET = ['GET']
POST = ['POST']
GET_POST = ['GET', 'POST']


def path(endpoint: Optional[str] = None) -> str:
    """Make a path pattern for a submission endpoint."""
    if endpoint is not None:
        return f'/<int:submission_id>/{endpoint}'
    return '/<int:submission_id>'


def handle(controller: Callable, template: str, title: str,
           submission_id: Optional[int] = None,
           get_params: bool = False, **kwargs) -> Response:
    """
    Generalized request handling pattern.

    Parameters
    ----------
    controller : callable
        A controller function with the signature ``(method: str, params:
        MultiDict, session: Session, submission_id: int, token: str) ->
        Tuple[dict, int, dict]``
    template : str
        HTML template to use in the response.
    title : str
        Page title, if not provided by controller.
    submission_id : int or None
    get_params : bool
        If True, GET parameters will be passed to the controller on GET
        requests. Default is False.
    kwargs : kwargs
        Passed as ``**kwargs`` to the controller.

    Returns
    -------
    :class:`.Response`

    """
    if request.method == 'GET' and get_params:
        request_data = MultiDict(request.args.items(multi=True))
    else:
        request_data = MultiDict(request.form.items(multi=True))
    data, code, headers = controller(request.method, request_data,
                                     request.session, submission_id, **kwargs)
    if 'pagetitle' not in data:
        data['pagetitle'] = title
    if code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]:
        return make_response(render_template(template, **data), code)
    if 'Location' in headers:
        return redirect(headers['Location'], code=code)
    return Response(response=data, status=code, headers=headers)


@ui.route('/', methods=GET_POST)
@auth.decorators.scoped(auth.scopes.CREATE_SUBMISSION)
def create_submission():
    """Create a new submission."""
    return handle(controllers.create.create, 'submit/create.html',
                  'Create a new submission')


@ui.route(path('delete'), methods=GET_POST)
@auth.decorators.scoped(auth.scopes.DELETE_SUBMISSION)
def delete_submission(submission_id: int):
    """Delete, or roll a submission back to the last published state."""
    return handle(controllers.delete.delete,
                  'submit/confirm_delete_submission.html',
                  'Delete submission or replacement')


@ui.route(path('replace'), methods=POST)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION)
def create_replacement(submission_id: int):
    """Create a replacement submission."""
    return handle(controllers.create.replace, 'submit/replace.html',
                  'Create a new version (replacement)')


@ui.route(path(), methods=GET)
@auth.decorators.scoped(auth.scopes.VIEW_SUBMISSION, authorizer=is_owner)
def submission_status(submission_id: int) -> Response:
    """Display the current state of the submission."""
    return handle(controllers.submission_status, 'submit/status.html',
                  'Submission status', submission_id)


# TODO: remove me!!
@ui.route(path('publish'), methods=GET)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner)
def publish(submission_id: int) -> Response:
    """WARNING WARNING WARNING this is for testing purposes only."""
    util.publish_submission(submission_id)
    target = url_for('ui.submission_status', submission_id=submission_id)
    return Response(response={}, status=status.HTTP_303_SEE_OTHER,
                    headers={'Location': target})


# TODO: remove me!!
@ui.route(path('/place_on_hold'), methods=GET)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner)
def place_on_hold(submission_id: int) -> Response:
    """WARNING WARNING WARNING this is for testing purposes only."""
    util.place_on_hold(submission_id)
    target = url_for('ui.submission_status', submission_id=submission_id)
    return Response(response={}, status=status.HTTP_303_SEE_OTHER,
                    headers={'Location': target})


# TODO: remove me!!
@ui.route(path('apply_cross'), methods=GET)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner)
def apply_cross(submission_id: int) -> Response:
    """WARNING WARNING WARNING this is for testing purposes only."""
    util.apply_cross(submission_id)
    target = url_for('ui.submission_status', submission_id=submission_id)
    return Response(response={}, status=status.HTTP_303_SEE_OTHER,
                    headers={'Location': target})


# TODO: remove me!!
@ui.route(path('reject_cross'), methods=GET)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner)
def reject_cross(submission_id: int) -> Response:
    """WARNING WARNING WARNING this is for testing purposes only."""
    util.reject_cross(submission_id)
    target = url_for('ui.submission_status', submission_id=submission_id)
    return Response(response={}, status=status.HTTP_303_SEE_OTHER,
                    headers={'Location': target})


# TODO: remove me!!
@ui.route(path('apply_withdrawal'), methods=GET)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner)
def apply_withdrawal(submission_id: int) -> Response:
    """WARNING WARNING WARNING this is for testing purposes only."""
    util.apply_withdrawal(submission_id)
    target = url_for('ui.submission_status', submission_id=submission_id)
    return Response(response={}, status=status.HTTP_303_SEE_OTHER,
                    headers={'Location': target})


# TODO: remove me!!
@ui.route(path('reject_withdrawal'), methods=GET)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner)
def reject_withdrawal(submission_id: int) -> Response:
    """WARNING WARNING WARNING this is for testing purposes only."""
    util.reject_withdrawal(submission_id)
    target = url_for('ui.submission_status', submission_id=submission_id)
    return Response(response={}, status=status.HTTP_303_SEE_OTHER,
                    headers={'Location': target})


@ui.route(path('verify_user'), endpoint=Stages.VERIFY_USER.value,
          methods=GET_POST)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner)
@flow_control(Stages.VERIFY_USER)
def verify(submission_id: Optional[int] = None) -> Response:
    """Render the submit start page."""
    return handle(controllers.verify_user.verify, 'submit/verify_user.html',
                  'Verify User Information', submission_id)


@ui.route(path('authorship'), endpoint=Stages.AUTHORSHIP.value,
          methods=GET_POST)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=is_owner)
@flow_control(Stages.AUTHORSHIP)
def authorship(submission_id: int) -> Response:
    """Render step 2, authorship."""
    return handle(controllers.authorship.authorship, 'submit/authorship.html',
                  'Confirm Authorship', submission_id)


@ui.route(path('license'), endpoint=Stages.LICENSE.value, methods=GET_POST)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner)
@flow_control(Stages.LICENSE)
def license(submission_id: int) -> Response:
    """Render step 3, select license."""
    return handle(controllers.license.license, 'submit/license.html',
                  'Select a License', submission_id)


@ui.route(path('policy'), endpoint=Stages.POLICY.value, methods=GET_POST)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner)
@flow_control(Stages.POLICY)
def policy(submission_id: int) -> Response:
    """Render step 4, policy agreement."""
    return handle(controllers.policy.policy, 'submit/policy.html',
                  'Acknowledge Policy Statement', submission_id)


@ui.route(path('classification'), endpoint=Stages.CLASSIFICATION.value,
          methods=GET_POST)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner)
@flow_control(Stages.CLASSIFICATION)
def classification(submission_id: int) -> Response:
    """Render step 5, choose classification."""
    return handle(controllers.classification.classification,
                  'submit/classification.html',
                  'Choose a Primary Classification', submission_id)


@ui.route(path('cross'), endpoint=Stages.CROSS_LIST.value, methods=GET_POST)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=is_owner)
@flow_control(Stages.CROSS_LIST)
def cross_list(submission_id: int) -> Response:
    """Render step 6, secondary classes."""
    return handle(controllers.classification.cross_list,
                  'submit/cross_list.html',
                  'Choose Cross-List Classifications', submission_id)


@ui.route(path('upload'), endpoint=Stages.FILE_UPLOAD.value, methods=GET_POST)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner)
@flow_control(Stages.FILE_UPLOAD)
def file_upload(submission_id: int) -> Response:
    """Render step 7, file upload."""
    return handle(controllers.upload_files, 'submit/file_upload.html',
                  'Upload Files', submission_id, files=request.files,
                  token=request.environ['token'])


@ui.route(path('file_delete'), methods=GET_POST)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner)
@flow_control(Stages.FILE_UPLOAD)
def file_delete(submission_id: int) -> Response:
    """Provide the file deletion endpoint, part of the upload step."""
    return handle(controllers.delete_file, 'submit/confirm_delete.html',
                  'Delete File', submission_id, get_params=True,
                  token=request.environ['token'])


@ui.route(path('file_delete_all'), methods=GET_POST)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner)
@flow_control(Stages.FILE_UPLOAD)
def file_delete_all(submission_id: int) -> Response:
    """Provide endpoint to delete all files, part of the upload step."""
    return handle(controllers.delete_all_files,
                  'submit/confirm_delete_all.html',  'Delete All Files',
                  submission_id, get_params=True,
                  token=request.environ['token'])


@ui.route(path('process'), endpoint=Stages.PROCESS.value, methods=GET_POST)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner)
@flow_control(Stages.PROCESS)
def file_process(submission_id: int) -> Response:
    """Render step 8, file processing."""
    return handle(controllers.process.file_process, 'submit/file_process.html',
                  'Process Files', submission_id, get_params=True,
                  token=request.environ['token'])


@ui.route(path('preview'), methods=GET)
@auth.decorators.scoped(auth.scopes.VIEW_SUBMISSION, authorizer=is_owner)
def file_preview(submission_id: int) -> Response:
    data, code, headers = controllers.file_preview(
        MultiDict(request.args.items(multi=True)),
        request.session,
        submission_id,
        request.environ['token']
    )
    return send_file(data, mimetype=headers['Content-Type'])


@ui.route(path('compilation_log'), methods=GET)
@auth.decorators.scoped(auth.scopes.VIEW_SUBMISSION, authorizer=is_owner)
def compilation_log(submission_id: int) -> Response:
    data, code, headers = controllers.compilation_log(
        MultiDict(request.args.items(multi=True)),
        request.session,
        submission_id,
        request.environ['token']
    )
    return send_file(data, mimetype=headers['Content-Type'])


@ui.route(path('metadata'), endpoint=Stages.METADATA.value, methods=GET_POST)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner)
@flow_control(Stages.METADATA)
def add_metadata(submission_id: int) -> Response:
    """Render step 9, metadata."""
    return handle(controllers.metadata.metadata, 'submit/add_metadata.html',
                  'Add or Edit Metadata', submission_id)


@ui.route(path('optional'), endpoint=Stages.OPTIONAL.value, methods=GET_POST)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner)
@flow_control(Stages.OPTIONAL)
def add_optional_metadata(submission_id: int) -> Response:
    """Render step 9, metadata."""
    return handle(controllers.metadata.optional,
                  'submit/add_optional_metadata.html',
                  'Add or Edit Metadata', submission_id)


@ui.route(path('finalize'), endpoint=Stages.FINAL_PREVIEW.value, methods=GET)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner)
@flow_control(Stages.FINAL_PREVIEW)
def final_preview(submission_id: int) -> Response:
    """Render step 10, preview."""
    return handle(controllers.final.finalize, 'submit/final_preview.html',
                  'Preview and Approve', submission_id)


@ui.route(path('confirm_submit'), methods=['GET'])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner)
def confirm_submit(submission_id: int) -> Response:
    """Render the final confirmation page."""
    rendered = render_template("submit/confirm_submit.html",
                               pagetitle='Submission Confirmed')
    return make_response(rendered, status.HTTP_200_OK)

# Other workflows.


@ui.route(path('jref'), methods=GET_POST)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=is_owner)
def jref(submission_id: Optional[int] = None) -> Response:
    """Render the JREF submission page."""
    return handle(controllers.jref.jref, 'submit/jref.html',
                  'Add journal reference', submission_id)


@ui.route(path('withdraw'), methods=GET_POST)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=is_owner)
def withdraw(submission_id: Optional[int] = None) -> Response:
    """Render the withdrawal request page."""
    return handle(controllers.withdraw.request_withdrawal,
                  'submit/withdraw.html', 'Request withdrawal', submission_id)


@ui.route(path('request_cross'), methods=GET_POST)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION,
                        authorizer=is_owner)
def request_cross(submission_id: Optional[int] = None) -> Response:
    """Render the cross-list request page."""
    return handle(controllers.cross.request_cross,
                  'submit/request_cross_list.html', 'Request cross-list',
                  submission_id)


def inject_get_next_stage_for_submission() -> Dict[str, Callable]:
    """Inject information about the next stage in the process."""
    def get_next_stage_for_submission(this_submission: Submission) -> str:
        if this_submission.version == 1:
            stage = SubmissionStage(this_submission)
        else:
            stage = ReplacementStage(this_submission)
        return url_for(f'ui.{stage.next_stage.value}',
                       submission_id=this_submission.submission_id)
    return {'get_next_stage_for_submission': get_next_stage_for_submission}


@ui.app_template_filter()
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
    if len(endorsements) == 0:
        return 'None'
    elif '*.*' in endorsements:
        return 'All'
    return 'Some'
