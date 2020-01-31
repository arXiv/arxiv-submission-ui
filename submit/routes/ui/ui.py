"""Provides routes for the submission user interface."""

from http import HTTPStatus as status
from typing import Optional, Callable, Dict, List, Union, Any

from flask import Blueprint, make_response, redirect, request, Markup, \
                  render_template, url_for, g, send_file, session
from flask import Response as FResponse
from werkzeug import MultiDict
from werkzeug import Response as WResponse
from werkzeug.exceptions import InternalServerError, BadRequest, \
    ServiceUnavailable

import arxiv.submission as events
from arxiv import taxonomy
from arxiv.base import logging, alerts
from arxiv.users import auth
from arxiv.submission.domain import Submission
from arxiv.submission.services.classic.exceptions import Unavailable

from ..auth import is_owner
from ... import util
from submit.controllers import ui
#from ...domain import workflow
from .workflow import Authorship, BaseStage, Classification, Confirm, \
    CrossList, FileUpload, FinalPreview, License, Metadata, OptionalMetadata, Policy, \
    Process, ReplacementWorkflow, Stage, SubmissionWorkflow, VerifyUser, \
    Workflow, stage_from_endpoint


from .flow_control import flow_control, get_workflow

logger = logging.getLogger(__name__)

UI = Blueprint('ui', __name__, url_prefix='/')

SUPPORT = Markup(
    'If you continue to experience problems, please contact'
    ' <a href="mailto:help@arxiv.org"> arXiv support</a>.'
)

Response = Union[FResponse, WResponse]


def path(endpoint: Optional[str] = None) -> str:
    """Make a path pattern for a submission endpoint."""
    if endpoint is not None:
        return f'/<int:submission_id>/{endpoint}'
    return '/<int:submission_id>'


def workflow_route(stage: Stage, methods=["GET", "POST"]) -> Callable:
    """Register a UI route for a workflow stage."""
    def deco(func: Callable) -> Callable:
        kwargs = {'endpoint': stage.endpoint, 'methods': methods}
        return UI.route(path(stage.endpoint), **kwargs)(func)
    return deco


def redirect_to_login(*args, **kwargs) -> str:
    """Send the unauthorized user to the log in page."""
    return redirect(url_for('login'))


@UI.before_request
def load_submission() -> None:
    """Load the submission before the request is processed."""
    if request.view_args is None or 'submission_id' not in request.view_args:
        return
    submission_id = request.view_args['submission_id']
    try:
        request.submission, request.events = \
            util.load_submission(submission_id)
    except Unavailable as e:
        raise ServiceUnavailable('Could not connect to database') from e


@UI.context_processor
def inject_stage() -> Dict[str, Optional[Stage]]:
    """Inject the current stage into the template rendering context."""
    if request.url_rule is None:
        return {}
    endpoint = request.url_rule.endpoint
    if '.' in endpoint:
        _, endpoint = endpoint.split('.', 1)
    stage: Optional[Stage]
    try:
        stage = stage_from_endpoint(endpoint)
    except ValueError:
        stage = None

    def get_current_stage_for_submission(submission: Submission) -> str:
        """Get the endpoint of the current step for a submission."""
        return get_workflow(submission).current_stage.endpoint

    return {
        'this_stage': stage,
        'get_current_stage_for_submission': get_current_stage_for_submission
    }


@UI.context_processor
def inject_workflow() -> Dict[str, Optional[Workflow]]:
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
           get_params: bool = False, **kwargs: Any) -> Response:
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
    response: Response
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
        assert isinstance(e.description, dict)
        context.update(e.description)
        context.update({'error': e})
        message = Markup(f'Something unexpected went wrong. {SUPPORT}')
        add_immediate_alert(context, alerts.FAILURE, message)
        response = make_response(render_template(template, **context), e.code)
        return response
    except Unavailable as e:
        raise ServiceUnavailable('Could not connect to database') from e
    context.update(data)

    if code < 300:
        response = make_response(render_template(template, **context), code)
    elif 'Location' in headers:
        response = redirect(headers['Location'], code=code)
    else:
        response = FResponse(response=context, status=code, headers=headers)
    return response


@UI.route('/status', methods=['GET'])
def service_status():
    """Status endpoint."""
    return 'ok'


@UI.route('/', methods=["GET"])
@auth.decorators.scoped(auth.scopes.CREATE_SUBMISSION,
                        unauthorized=redirect_to_login)
def manage_submissions():
    """Display the submission management dashboard."""
    return handle(ui.new.create.create, 'submit/manage_submissions.html',
                  'Manage submissions')


@UI.route('/', methods=["POST"])
@auth.decorators.scoped(auth.scopes.CREATE_SUBMISSION,
                        unauthorized=redirect_to_login)
def create_submission():
    """Create a new submission."""
    return handle(ui.create.create, 'submit/manage_submissions.html',
                  'Create a new submission')


@UI.route(path('unsubmit'), methods=["GET", "POST"])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
def unsubmit_submission(submission_id: int):
    """Unsubmit (unfinalize) a submission."""
    return handle(ui.new.unsubmit.unsubmit,
                  'submit/confirm_unsubmit.html',
                  'Unsubmit submission', submission_id)


@UI.route(path('delete'), methods=["GET", "POST"])
@auth.decorators.scoped(auth.scopes.DELETE_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
def delete_submission(submission_id: int):
    """Delete, or roll a submission back to the last announced state."""
    return handle(ui.delete.delete,
                  'submit/confirm_delete_submission.html',
                  'Delete submission or replacement', submission_id)


@UI.route(path('cancel/<string:request_id>'), methods=["GET", "POST"])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
def cancel_request(submission_id: int, request_id: str):
    """Cancel a pending request."""
    return handle(ui.delete.cancel_request,
                  'submit/confirm_cancel_request.html', 'Cancel request',
                  submission_id, request_id=request_id)


@UI.route(path('replace'), methods=["POST"])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
def create_replacement(submission_id: int):
    """Create a replacement submission."""
    return handle(ui.new.create.replace, 'submit/replace.html',
                  'Create a new version (replacement)', submission_id)


@UI.route(path(), methods=["GET"])
@auth.decorators.scoped(auth.scopes.VIEW_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
def submission_status(submission_id: int) -> Response:
    """Display the current state of the submission."""
    return handle(ui.submission_status, 'submit/status.html',
                  'Submission status', submission_id)


# # TODO: remove me!!
# @UI.route(path('announce'), methods=["GET"])
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
# @UI.route(path('/place_on_hold'), methods=["GET"])
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
# @UI.route(path('apply_cross'), methods=["GET"])
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
# @UI.route(path('reject_cross'), methods=["GET"])
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
# @UI.route(path('apply_withdrawal'), methods=["GET"])
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
# @UI.route(path('reject_withdrawal'), methods=["GET"])
# @auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner)
# def reject_withdrawal(submission_id: int) -> Response:
#     """WARNING WARNING WARNING this is for testing purposes only."""
#     util.reject_withdrawal(submission_id)
#     target = url_for('ui.submission_status', submission_id=submission_id)
#     return Response(response={}, status=status.SEE_OTHER,
#                     headers={'Location': target})


@workflow_route(VerifyUser)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
@flow_control(VerifyUser)
def verify(submission_id: Optional[int] = None) -> Response:
    """Render the submit start page."""
    return handle(ui.new.verify_user.verify, 'submit/verify_user.html',
                  'Verify User Information', submission_id)


@workflow_route(Authorship)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
@flow_control(Authorship)
def authorship(submission_id: int) -> Response:
    """Render step 2, authorship."""
    return handle(ui.new.authorship.authorship, 'submit/authorship.html',
                  'Confirm Authorship', submission_id)


@workflow_route(License)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
@flow_control(License)
def license(submission_id: int) -> Response:
    """Render step 3, select license."""
    return handle(ui.new.license.license, 'submit/license.html',
                  'Select a License', submission_id)


@workflow_route(Policy)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
@flow_control(Policy)
def policy(submission_id: int) -> Response:
    """Render step 4, policy agreement."""
    return handle(ui.new.policy.policy, 'submit/policy.html',
                  'Acknowledge Policy Statement', submission_id)


@workflow_route(Classification)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
@flow_control(Classification)
def classification(submission_id: int) -> Response:
    """Render step 5, choose classification."""
    return handle(ui.new.classification.classification,
                  'submit/classification.html',
                  'Choose a Primary Classification', submission_id)


@workflow_route(CrossList)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
@flow_control(CrossList)
def cross_list(submission_id: int) -> Response:
    """Render step 6, secondary classes."""
    return handle(ui.new.classification.cross_list,
                  'submit/cross_list.html',
                  'Choose Cross-List Classifications', submission_id)


@workflow_route(FileUpload)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
@flow_control(FileUpload)
def file_upload(submission_id: int) -> Response:
    """Render step 7, file upload."""
    return handle(ui.new.upload.upload_files, 'submit/file_upload.html',
                  'Upload Files', submission_id, files=request.files,
                  token=request.environ['token'])


@UI.route(path('file_delete'), methods=["GET", "POST"])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
@flow_control(FileUpload)
def file_delete(submission_id: int) -> Response:
    """Provide the file deletion endpoint, part of the upload step."""
    return handle(ui.delete_file, 'submit/confirm_delete.html',
                  'Delete File', submission_id, get_params=True,
                  token=request.environ['token'])


@UI.route(path('file_delete_all'), methods=["GET", "POST"])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
@flow_control(FileUpload)
def file_delete_all(submission_id: int) -> Response:
    """Provide endpoint to delete all files, part of the upload step."""
    return handle(ui.delete_all_files,
                  'submit/confirm_delete_all.html',  'Delete All Files',
                  submission_id, get_params=True,
                  token=request.environ['token'])


@workflow_route(Process)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
@flow_control(Process)
def file_process(submission_id: int) -> Response:
    """Render step 8, file processing."""
    return handle(ui.new.process.file_process, 'submit/file_process.html',
                  'Process Files', submission_id, get_params=True,
                  token=request.environ['token'])


@UI.route(path('preview.pdf'), methods=["GET"])
@auth.decorators.scoped(auth.scopes.VIEW_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
def file_preview(submission_id: int) -> Response:
    data, code, headers = ui.new.process.file_preview(
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


@UI.route(path('compilation_log'), methods=["GET"])
@auth.decorators.scoped(auth.scopes.VIEW_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
def compilation_log(submission_id: int) -> Response:
    data, code, headers = ui.new.process.compilation_log(
        MultiDict(request.args.items(multi=True)),
        request.auth,
        submission_id,
        request.environ['token']
    )
    rv = send_file(data, mimetype=headers['Content-Type'], cache_timeout=0)
    rv.set_etag(headers['ETag'])
    rv.headers['Cache-Control'] = 'no-store'
    return rv


@workflow_route(Metadata)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
@flow_control(Metadata)
def add_metadata(submission_id: int) -> Response:
    """Render step 9, metadata."""
    return handle(ui.new.metadata.metadata, 'submit/add_metadata.html',
                  'Add or Edit Metadata', submission_id)


@workflow_route(OptionalMetadata)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
@flow_control(OptionalMetadata)
def add_optional_metadata(submission_id: int) -> Response:
    """Render step 9, metadata."""
    return handle(ui.new.metadata.optional,
                  'submit/add_optional_metadata.html',
                  'Add or Edit Metadata', submission_id)


@workflow_route(FinalPreview)
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
@flow_control(FinalPreview)
def final_preview(submission_id: int) -> Response:
    """Render step 10, preview."""
    return handle(ui.new.final.finalize, 'submit/final_preview.html',
                  'Preview and Approve', submission_id)


@workflow_route(Confirm, methods=["GET"])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
@flow_control(Confirm)
def confirmation(submission_id: int) -> Response:
    """Render the final confirmation page."""
    return handle(ui.new.final.confirm, "submit/confirm_submit.html",
                  'Submission Confirmed',
                  submission_id)

# Other workflows.


@UI.route(path('jref'), methods=["GET", "POST"])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
def jref(submission_id: Optional[int] = None) -> Response:
    """Render the JREF submission page."""
    return handle(ui.jref.jref, 'submit/jref.html',
                  'Add journal reference', submission_id)


@UI.route(path('withdraw'), methods=["GET", "POST"])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
def withdraw(submission_id: Optional[int] = None) -> Response:
    """Render the withdrawal request page."""
    return handle(ui.withdraw.request_withdrawal,
                  'submit/withdraw.html', 'Request withdrawal', submission_id)


@UI.route(path('request_cross'), methods=["GET", "POST"])
@auth.decorators.scoped(auth.scopes.EDIT_SUBMISSION, authorizer=is_owner,
                        unauthorized=redirect_to_login)
def request_cross(submission_id: Optional[int] = None) -> Response:
    """Render the cross-list request page."""
    return handle(ui.cross.request_cross,
                  'submit/request_cross_list.html', 'Request cross-list',
                  submission_id)

@UI.route('/testalerts')
def testalerts() -> Response:
    tc = {}
    request.submission, request.events = util.load_submission(1)
    wfp = get_workflow(request.submission)
    request.workflow = wfp
    request.current_stage = wfp.current_stage()
    request.this_stage = wfp.workflow[endpoint_name()]

    tc['workflow'] = wfp
    tc['submission_id'] = 1

    add_immediate_alert(tc, 'WARNING', 'This is a warning to you from the normal submission alert system.', "SUBMISSION ALERT TITLE")
    alerts.flash_failure('This is one of those alerts from base alert(): you failed', 'BASE ALERT')
    return make_response(render_template('submit/testalerts.html', **tc), 200)


@UI.app_template_filter()
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
