"""Defines submission stages and workflows supported by this UI."""

from typing import Iterable, MutableMapping, NamedTuple, Optional, Dict, \
    Union, Callable, List, Iterator
from functools import wraps
from arxiv.submission.domain import Submission
from arxiv.submission.domain.submission import SubmissionContent


class Stage(type):     # type: ignore
    """Stages in the submission UI workflow."""


class BaseStage(metaclass=Stage):
    """Base class for workflow stages."""

    endpoint: str
    label: str
    title: str
    display: str
    requested: bool
    must_see: bool

    def __init__(self, required: bool = True, must_see: bool = False) -> None:
        """
        Configure the stage for a particular workflow.

        Parameters
        ----------
        required : bool
            This stage must be complete to proceed.
        must_see : bool
            This stage must be seen (even if already complete) to proceed.

        """
        self.required = required
        self.must_see = must_see

    def is_optional(self) -> bool:
        """Inverse of :attr:`.required`."""
        return bool(not self.required)

    @property
    def type(self) -> Stage:
        """Convenience method for getting type; to support use in templates."""
        return type(self)


def stage_from_endpoint(endpoint: str) -> Stage:
    """Get the :class:`.Stage` for an endpoint."""
    for stage in BaseStage.__subclasses__():
        if stage.endpoint == endpoint:
            return stage
    raise ValueError(f'No stage for endpoint: {endpoint}')


class VerifyUser(BaseStage):
    """The user is asked to verify their personal information."""

    endpoint = 'verify_user'
    label = 'verify your personal information'
    title = 'Verify user info'
    display = 'Verify User'

    @staticmethod
    def is_complete(submission: Submission) -> bool:
        """Determine whether the submitter has verified their information."""
        return submission.submitter_contact_verified is True


class Authorship(BaseStage):
    """The user is asked to verify their authorship status."""

    endpoint = 'authorship'
    label = 'confirm authorship'
    title = "Confirm authorship"
    display = "Authorship"

    @staticmethod
    def is_complete(submission: Submission) -> bool:
        """Determine whether the submitter has indicated authorship."""
        return submission.submitter_is_author is not None


class License(BaseStage):
    """The user is asked to select a license."""

    endpoint = 'license'
    label = 'choose a license'
    title = "Choose license"
    display = "License"

    @staticmethod
    def is_complete(submission: Submission) -> bool:
        """Determine whether the submitter has selected a license."""
        return submission.license is not None


class Policy(BaseStage):
    """The user is required to agree to arXiv policies."""

    endpoint = 'policy'
    label = 'accept arXiv submission policies'
    title = "Acknowledge policy"
    display = "Policy"

    @staticmethod
    def is_complete(submission: Submission) -> bool:
        """Determine whether the submitter has accepted arXiv policies."""
        return submission.submitter_accepts_policy is True


class Classification(BaseStage):
    """The user is asked to select a primary category."""

    endpoint = 'classification'
    label = 'select a primary category'
    title = "Choose category"
    display = "Category"

    @staticmethod
    def is_complete(submission: Submission) -> bool:
        """Determine whether the submitter selected a primary category."""
        return submission.primary_classification is not None


class CrossList(BaseStage):
    """The user is given the option of selecting cross-list categories."""

    endpoint = 'cross_list'
    label = 'add cross-list categories'
    title = "Add cross-list"
    display = "Cross-list"

    @staticmethod
    def is_complete(submission: Submission) -> bool:
        return len(submission.secondary_classification) > 0


class FileUpload(BaseStage):
    """The user is asked to upload files for their submission."""

    endpoint = 'file_upload'
    label = 'upload your submission files'
    title = "File upload"
    display = "Upload Files"
    always_check = True

    @staticmethod
    def is_complete(submission: Submission) -> bool:
        """Determine whether the submitter has uploaded files."""
        return submission.source_content is not None and \
            submission.source_content.checksum is not None and \
            submission.source_content.source_format != SubmissionContent.Format.INVALID


class Process(BaseStage):
    """Uploaded files are processed; this is primarily to compile LaTeX."""

    endpoint = 'file_process'
    label = 'process your submission files'
    title = "File process"
    display = "Process Files"
    """We need to re-process every time the source is updated."""

    @staticmethod
    def is_complete(submission: Submission) -> bool:
        """Determine whether the submitter has compiled their upload."""
        return bool(submission.is_source_processed)



class Metadata(BaseStage):
    """The user is asked to require core metadata fields, like title."""

    endpoint = 'add_metadata'
    label = 'add required metadata'
    title = "Add metadata"
    display = "Metadata"

    @staticmethod
    def is_complete(submission: Submission) -> bool:
        """Determine whether the submitter has entered required metadata."""
        return (submission.metadata.title is not None
                and submission.metadata.abstract is not None
                and submission.metadata.authors_display is not None)


class OptionalMetadata(BaseStage):
    """The user is given the option of entering optional metadata."""

    endpoint = 'add_optional_metadata'
    label = 'add optional metadata'
    title = "Add optional metadata"
    display = "Opt. Metadata"

    @staticmethod
    def is_complete(submission: Submission) -> bool:
        """Determine whether the user has set optional metadata fields."""
        return (submission.metadata.doi is not None
                or submission.metadata.msc_class is not None
                or submission.metadata.acm_class is not None
                or submission.metadata.report_num is not None
                or submission.metadata.journal_ref is not None)


class FinalPreview(BaseStage):
    """The user is asked to review the submission before finalizing."""

    endpoint = 'final_preview'
    label = 'preview and approve your submission'
    title = "Final preview"
    display = "Preview"

    @staticmethod
    def is_complete(submission: Submission) -> bool:
        """Determine whether the submission is finalized."""
        return bool(submission.is_finalized)


class Confirm(BaseStage):
    """The submission is confirmed."""

    endpoint = 'confirmation'
    label = 'your submission is confirmed'
    title = "Submission confirmed"
    display = "Confirmed"

    @staticmethod
    def is_complete(submission: Submission) -> bool:
        return False


def get_instance(func: Callable) -> Callable:
    """Look up the stage instance before calling ``func``."""
    @wraps(func)
    def inner(workflow: 'Workflow', stage: Optional[Union[Stage, BaseStage]]):
        if stage and not isinstance(stage, BaseStage):
            idx = workflow._order.index(stage)
            stage: BaseStage = workflow.ORDER[idx]
        return func(workflow, stage)
    return inner


class Workflow:

    ORDER: List[BaseStage] = []
    CONFIRMATION: Optional[Stage] = None

    def __init__(self, submission: Submission, seen: MutableMapping) -> None:
        """
        Initialize for a specific submission, and a mapping for seen stages.

        Parameters
        ----------
        submission : :class:`.Submission`
            The submission that is subject to this workflow.
        seen : mapping
            A mapping that we can use to track what stages the user has seen
            for a particular submission and workflow. For example, this could
            be a client session.

        """
        self.submission = submission
        self._seen = seen
        self._key = f'{submission.submission_id}::{self.__class__.__name__}'
        self._order = [type(stage) for stage in self.ORDER]

    def __iter__(self) -> Iterator[BaseStage]:
        """Iterate over stages in this workflow."""
        for stage in self.ORDER:
            yield stage

    def iter_prior(self, stage: Stage) -> Iterable[BaseStage]:
        """Iterate over stages in this workflow up to a particular stage."""
        for prior_stage in self:
            if prior_stage == stage:
                return
            yield prior_stage

    @property
    def complete(self) -> bool:
        """Determine whether this workflow is complete."""
        return bool(self.submission.is_finalized)

    @property
    def current_stage(self) -> Optional[BaseStage]:
        """Get the first stage in the workflow that is not done."""
        for stage in self:
            if not self.is_done(stage):
                return stage
        return None

    @property
    def confirmation(self) -> Stage:
        """Get the confirmation :class:`.Stage` for this workflow."""
        assert self.CONFIRMATION is not None
        return self.CONFIRMATION

    @get_instance
    def next_stage(self, stage: Optional[BaseStage]) -> Optional[BaseStage]:
        """Get the next stage."""
        if stage is None:
            return None
        idx = self.ORDER.index(stage)
        if idx + 1 >= len(self.ORDER):
            return None
        return self.ORDER[idx + 1]

    @get_instance
    def previous_stage(self, stage: Optional[BaseStage]) -> Optional[BaseStage]:
        """Get the previous stage."""
        if stage is None:
            return None
        idx = self.ORDER.index(stage)
        if idx == 0:
            return None
        return self.ORDER[idx - 1]

    @get_instance
    def can_proceed_to(self, stage: Optional[BaseStage]) -> bool:
        """Determine whether the user can proceed to a stage."""
        return self.is_done(self.previous_stage(stage)) \
            or (self.previous_stage(stage).is_optional()
                and all(map(self.is_done,
                            self.iter_prior(self.previous_stage(stage))))) \
            or all(map(self.is_done, self.iter_prior(stage)))

    @get_instance
    def is_required(self, stage: Optional[BaseStage]) -> bool:
        """Check whether a stage is required."""
        if stage is None:
            return False
        return stage.required

    @get_instance
    def is_complete(self, stage: Optional[BaseStage]) -> bool:
        """Determine whether or not a stage is complete."""
        if stage is None:
            return True
        return stage.is_complete(self.submission)

    def mark_seen(self, stage: Stage) -> None:
        """Mark a stage as seen by the user."""
        try:
            seen = self._seen[self._key]
        except KeyError:
            seen = {}
        seen[stage.endpoint] = True
        self._seen[self._key] = seen

    def is_seen(self, stage: Optional[Stage]) -> bool:
        """Determine whether or not the user has seen this stage."""
        if stage is None:
            return True
        try:
            seen = self._seen[self._key]
        except KeyError:
            seen = {}
        return seen.get(stage.endpoint, False)

    @get_instance
    def is_done(self, stage: Optional[BaseStage]) -> bool:
        """
        Evaluate whether a stage is sufficiently addressed for this workflow.

        This considers whether the stage is complete (if required), and whether
        the stage has been seen (if it must be seen).
        """
        if stage is None:
            return True
        return ((self.is_complete(stage) or stage.is_optional())
                and (self.is_seen(stage) or not stage.must_see))


class SubmissionWorkflow(Workflow):
    """Workflow for new submissions."""

    ORDER = [
        VerifyUser(),
        Authorship(),
        License(),
        Policy(),
        Classification(),
        CrossList(required=False, must_see=True),
        FileUpload(),
        Process(),
        Metadata(),
        OptionalMetadata(required=False, must_see=True),
        FinalPreview(),
        Confirm()
    ]
    CONFIRMATION = Confirm


class ReplacementWorkflow(Workflow):
    """Workflow for replacements."""

    ORDER = [
        VerifyUser(must_see=True),
        Authorship(must_see=True),
        License(must_see=True),
        Policy(must_see=True),
        FileUpload(must_see=True),
        Process(must_see=True),
        Metadata(must_see=True),
        OptionalMetadata(required=False, must_see=True),
        FinalPreview(must_see=True),
        Confirm(must_see=True)
    ]
    CONFIRMATION = Confirm
