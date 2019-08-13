"""Provides routes for the submission user interface."""

from http import HTTPStatus as status
from typing import Optional, Callable, Dict, List, Union

from flask import Blueprint, make_response, redirect, request, Markup, \
                  render_template, url_for, Response, g, send_file, session
from werkzeug import MultiDict
from werkzeug.exceptions import InternalServerError, BadRequest

import arxiv.submission as events
from arxiv import taxonomy
from arxiv.base import logging, alerts
from arxiv.users import auth
from arxiv.submission.domain import Submission
from arxiv.submission.services.classic.exceptions import Unavailable

from .auth import is_owner
from .. import controllers, util
from ..domain import workflow
from ..flow_control import flow_control, get_workflow

logger = logging.getLogger(__name__)

ui = Blueprint('ui', __name__, url_prefix='/')

SUPPORT = Markup(
    'If you continue to experience problems, please contact'
    ' <a href="mailto:help@arxiv.org"> arXiv support</a>.'
)


def path(endpoint: Optional[str] = None) -> str:
    """Make a path pattern for a submission endpoint."""
    if endpoint is not None:
        return f'/<int:submission_id>/{endpoint}'
    return '/<int:submission_id>'


def workflow_route(stage: workflow.Stage, methods=["GET", "POST"]) -> Callable:
    """Register a UI route for a workflow stage."""
    def deco(func: Callable) -> Callable:
        kwargs = {'endpoint': stage.endpoint, 'methods': methods}
        return ui.route(path(stage.endpoint), **kwargs)(func)
    return deco


def redirect_to_login(*args, **kwargs) -> str:
    """Send the unauthorized user to the log in page."""
    return redirect(url_for('login'))


@ui.before_request
def load_submission() -> None:
    """Load the submission before the request is processed."""
    if request.view_args is None or 'submission_id' not in request.view_args:
        return
    submission_id = request.view_args['submission_id']
    try:
        request.submission, request.events = \
            util.load_submission(submission_id)
    except Unavailable as e:
        raise InternalServerError('Could not connect to database') from e


@ui.context_processor
def inject_stage() -> Dict[str, Optional[workflow.Stage]]:
    """Inject the current stage into the template rendering context."""
    endpoint = request.url_rule.endpoint
    if '.' in endpoint:
        _, endpoint = endpoint.split('.', 1)
    try:
        stage = workflow.stage_from_endpoint(endpoint)
    except ValueError:
        stage = None

    def get_current_stage_for_submission(submission: Submission) -> str:
        """Get the endpoint of the current step for a submission."""
        return get_workflow(submission).current_stage.endpoint

    return {
        'this_stage': stage,
        'get_current_stage_for_submission': get_current_stage_for_submission
    }


@ui.context_processor
def inject_workflow() -> Dict[str, Optional[workflow.Workflow]]:
    """Inject the current workflow into the template rendering context."""
    if hasattr(request, 'submission'):
        return {'workflow': get_workflow(request.submission)}
    return {'workflow': None, 'get_workflow': get_workflow}


def add_immediate_alert(context: dict, severity: str,
                        message: Union[str, dict], title: Optional[str] = None,
                        dismissable: bool = True, safe: bool = False) -> None:
    """Add an alert for immediate display."""
    if safe and isinstance(message, str):
        message = Markup(message)
    data = {'message': message, 'title': title, 'dismissable': dismissable}

    if 'immediate_alerts' not in context:
        context['immediate_alerts'] = []
    context['immediate_alerts'].append((severity, data))


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
    logger.debug('Handle call to controller %s with template %s, title %s,'
                 ' and ID %s', controller, template, title, submission_id)
    if request.method == 'GET' and get_params:
        request_data = MultiDict(request.args.items(multi=True))
    else:
        request_data = MultiDict(request.form.items(multi=True))

    context = {'pagetitle': title}
    try:
        data, code, headers = controller(request.method, request_data,
                                         request.auth, submission_id,
                                         **kwargs)
    except (BadRequest, InternalServerError) as e:
        logger.debug('Caught %s from controller', e)
        context.update(e.description)
        context.update({'error': e})
        message = Markup(f'Something unexpected went wrong. {SUPPORT}')
        add_immediate_alert(context, alerts.FAILURE, message)
        return make_response(render_template(template, **context), e.code)
    except Unavailable as e:
        raise InternalServerError('Could not connect to database') from e
    context.update(data)

    if code < 300:
        return make_response(render_template(template, **context), code)
    if 'Location' in headers:
        return redirect(headers['Location'], code=code)
    return Response(response=context, status=code, headers=headers)


@ui.route('/status', methods=['GET'])
def service_status():
    """Status endpoint."""
    return 'ok'


@ui.route('/', methods=["GET"])
@auth.decorators.scoped(auth.scopes.CREATE_SUBMISSION,
                        unauthorized=redirect_to_login)
def manage_submissions():
    """Display the submission management dashboard."""
    return handle(controllers.create.create, 'submit/manage_submissions.html',
                  'Manage submissions')


@ui.route('/', methods=["POST"])
@auth.decorators.scoped(auth.scopes.CREATE_SUBMISSION,
                        unauthorized=redirect_to_login)
def create_submission():
    """Create a new submission."""
    return handle(controllers.create.create, 'submit/manage_submissions.html',
                  'Create a new submission')


@ui.route(path('unsubmit'), methods=["GET", "POST"])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
def unsubmit_submission(submission_id: int):
    """Unsubmit (unfinalize) a submission."""
    return handle(controllers.unsubmit.unsubmit,
                  'submit/confirm_unsubmit.html',
                  'Unsubmit submission', submission_id)


@ui.route(path('delete'), methods=["GET", "POST"])
@auth.decorators.scoped(auth.scopes.DELETE_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
def delete_submission(submission_id: int):
    """Delete, or roll a submission back to the last announced state."""
    return handle(controllers.delete.delete,
                  'submit/confirm_delete_submission.html',
                  'Delete submission or replacement', submission_id)


@ui.route(path('cancel/<string:request_id>'), methods=["GET", "POST"])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
def cancel_request(submission_id: int, request_id: str):
    """Cancel a pending request."""
    return handle(controllers.delete.cancel_request,
                  'submit/confirm_cancel_request.html', 'Cancel request',
                  submission_id, request_id=request_id)


@ui.route(path('replace'), methods=["POST"])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
def create_replacement(submission_id: int):
    """Create a replacement submission."""
    return handle(controllers.create.replace, 'submit/replace.html',
                  'Create a new version (replacement)', submission_id)


@ui.route(path(), methods=["GET"])
@auth.decorators.scoped(auth.scopes.VIEW_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
def submission_status(submission_id: int) -> Response:
    """Display the current state of the submission."""
    return handle(controllers.submission_status, 'submit/status.html',
                  'Submission status', submission_id)


# # TODO: remove me!!
# @ui.route(path('announce'), methods=["GET"])
# @auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner)
# def announce(submission_id: int) -> Response:
#     """WARNING WARNING WARNING this is for testing purposes only."""
#     util.announce_submission(submission_id)
#     target = url_for('ui.submission_status', submission_id=submission_id)
#     return Response(response={}, status=status.SEE_OTHER,
#                     headers={'Location': target})
#
#
# # TODO: remove me!!
# @ui.route(path('/place_on_hold'), methods=["GET"])
# @auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner)
# def place_on_hold(submission_id: int) -> Response:
#     """WARNING WARNING WARNING this is for testing purposes only."""
#     util.place_on_hold(submission_id)
#     target = url_for('ui.submission_status', submission_id=submission_id)
#     return Response(response={}, status=status.SEE_OTHER,
#                     headers={'Location': target})
#
#
# # TODO: remove me!!
# @ui.route(path('apply_cross'), methods=["GET"])
# @auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner)
# def apply_cross(submission_id: int) -> Response:
#     """WARNING WARNING WARNING this is for testing purposes only."""
#     util.apply_cross(submission_id)
#     target = url_for('ui.submission_status', submission_id=submission_id)
#     return Response(response={}, status=status.SEE_OTHER,
#                     headers={'Location': target})
#
#
# # TODO: remove me!!
# @ui.route(path('reject_cross'), methods=["GET"])
# @auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner)
# def reject_cross(submission_id: int) -> Response:
#     """WARNING WARNING WARNING this is for testing purposes only."""
#     util.reject_cross(submission_id)
#     target = url_for('ui.submission_status', submission_id=submission_id)
#     return Response(response={}, status=status.SEE_OTHER,
#                     headers={'Location': target})
#
#
# # TODO: remove me!!
# @ui.route(path('apply_withdrawal'), methods=["GET"])
# @auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner)
# def apply_withdrawal(submission_id: int) -> Response:
#     """WARNING WARNING WARNING this is for testing purposes only."""
#     util.apply_withdrawal(submission_id)
#     target = url_for('ui.submission_status', submission_id=submission_id)
#     return Response(response={}, status=status.SEE_OTHER,
#                     headers={'Location': target})
#
#
# # TODO: remove me!!
# @ui.route(path('reject_withdrawal'), methods=["GET"])
# @auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner)
# def reject_withdrawal(submission_id: int) -> Response:
#     """WARNING WARNING WARNING this is for testing purposes only."""
#     util.reject_withdrawal(submission_id)
#     target = url_for('ui.submission_status', submission_id=submission_id)
#     return Response(response={}, status=status.SEE_OTHER,
#                     headers={'Location': target})


@workflow_route(workflow.VerifyUser)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
@flow_control(workflow.VerifyUser)
def verify(submission_id: Optional[int] = None) -> Response:
    """Render the submit start page."""
    return handle(controllers.verify_user.verify, 'submit/verify_user.html',
                  'Verify User Information', submission_id)


@workflow_route(workflow.Authorship)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
@flow_control(workflow.Authorship)
def authorship(submission_id: int) -> Response:
    """Render step 2, authorship."""
    return handle(controllers.authorship.authorship, 'submit/authorship.html',
                  'Confirm Authorship', submission_id)


@workflow_route(workflow.License)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
@flow_control(workflow.License)
def license(submission_id: int) -> Response:
    """Render step 3, select license."""
    return handle(controllers.license.license, 'submit/license.html',
                  'Select a License', submission_id)


@workflow_route(workflow.Policy)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
@flow_control(workflow.Policy)
def policy(submission_id: int) -> Response:
    """Render step 4, policy agreement."""
    return handle(controllers.policy.policy, 'submit/policy.html',
                  'Acknowledge Policy Statement', submission_id)


@workflow_route(workflow.Classification)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
@flow_control(workflow.Classification)
def classification(submission_id: int) -> Response:
    """Render step 5, choose classification."""
    return handle(controllers.classification.classification,
                  'submit/classification.html',
                  'Choose a Primary Classification', submission_id)


@workflow_route(workflow.CrossList)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
@flow_control(workflow.CrossList)
def cross_list(submission_id: int) -> Response:
    """Render step 6, secondary classes."""
    return handle(controllers.classification.cross_list,
                  'submit/cross_list.html',
                  'Choose Cross-List Classifications', submission_id)


@workflow_route(workflow.FileUpload)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
@flow_control(workflow.FileUpload)
def file_upload(submission_id: int) -> Response:
    """Render step 7, file upload."""
    return handle(controllers.upload_files, 'submit/file_upload.html',
                  'Upload Files', submission_id, files=request.files,
                  token=request.environ['token'])


@ui.route(path('file_delete'), methods=["GET", "POST"])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
@flow_control(workflow.FileUpload)
def file_delete(submission_id: int) -> Response:
    """Provide the file deletion endpoint, part of the upload step."""
    return handle(controllers.delete_file, 'submit/confirm_delete.html',
                  'Delete File', submission_id, get_params=True,
                  token=request.environ['token'])


@ui.route(path('file_delete_all'), methods=["GET", "POST"])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
@flow_control(workflow.FileUpload)
def file_delete_all(submission_id: int) -> Response:
    """Provide endpoint to delete all files, part of the upload step."""
    return handle(controllers.delete_all_files,
                  'submit/confirm_delete_all.html',  'Delete All Files',
                  submission_id, get_params=True,
                  token=request.environ['token'])


@workflow_route(workflow.Process)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
@flow_control(workflow.Process)
def file_process(submission_id: int) -> Response:
    """Render step 8, file processing."""
    return handle(controllers.process.file_process, 'submit/file_process.html',
                  'Process Files', submission_id, get_params=True,
                  token=request.environ['token'])


@ui.route(path('preview.pdf'), methods=["GET"])
@auth.decorators.scoped(auth.scopes.VIEW_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
def file_preview(submission_id: int) -> Response:
    data, code, headers = controllers.file_preview(
        MultiDict(request.args.items(multi=True)),
        request.auth,
        submission_id,
        request.environ['token']
    )
    rv = send_file(data, mimetype=headers['Content-Type'], cache_timeout=0)
    rv.set_etag(headers['ETag'])
    rv.headers['Content-Length'] = len(data)  # type: ignore
    rv.headers['Cache-Control'] = 'no-store'
    return rv


@ui.route(path('compilation_log'), methods=["GET"])
@auth.decorators.scoped(auth.scopes.VIEW_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
def compilation_log(submission_id: int) -> Response:
    data, code, headers = controllers.compilation_log(
        MultiDict(request.args.items(multi=True)),
        request.auth,
         submission_id,
        request.environ['token']
    )
    rv = send_file(data, mimetype=headers['Content-Type'], cache_timeout=0)
    rv.set_etag(headers['ETag'])
    response.headers['Cache-Control'] = 'no-store'
    return rv


@workflow_route(workflow.Metadata)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
@flow_control(workflow.Metadata)
def add_metadata(submission_id: int) -> Response:
    """Render step 9, metadata."""
    return handle(controllers.metadata.metadata, 'submit/add_metadata.html',
                  'Add or Edit Metadata', submission_id)


@workflow_route(workflow.OptionalMetadata)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
@flow_control(workflow.OptionalMetadata)
def add_optional_metadata(submission_id: int) -> Response:
    """Render step 9, metadata."""
    return handle(controllers.metadata.optional,
                  'submit/add_optional_metadata.html',
                  'Add or Edit Metadata', submission_id)


@workflow_route(workflow.FinalPreview)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
@flow_control(workflow.FinalPreview)
def final_preview(submission_id: int) -> Response:
    """Render step 10, preview."""
    return handle(controllers.final.finalize, 'submit/final_preview.html',
                  'Preview and Approve', submission_id)


@workflow_route(workflow.Confirm, methods=["GET"])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
@flow_control(workflow.Confirm)
def confirmation(submission_id: int) -> Response:
    """Render the final confirmation page."""
    return handle(controllers.final.confirm, "submit/confirm_submit.html", 'Submission Confirmed', submission_id)

# Other workflows.


@ui.route(path('jref'), methods=["GET", "POST"])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
def jref(submission_id: Optional[int] = None) -> Response:
    """Render the JREF submission page."""
    return handle(controllers.jref.jref, 'submit/jref.html',
                  'Add journal reference', submission_id)


@ui.route(path('withdraw'), methods=["GET", "POST"])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
def withdraw(submission_id: Optional[int] = None) -> Response:
    """Render the withdrawal request page."""
    return handle(controllers.withdraw.request_withdrawal,
                  'submit/withdraw.html', 'Request withdrawal', submission_id)


@ui.route(path('request_cross'), methods=["GET", "POST"])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
def request_cross(submission_id: Optional[int] = None) -> Response:
    """Render the cross-list request page."""
    return handle(controllers.cross.request_cross,
                  'submit/request_cross_list.html', 'Request cross-list',
                  submission_id)


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
