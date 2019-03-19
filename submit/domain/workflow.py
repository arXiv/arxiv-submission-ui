"""Defines submission stages and workflows supported by this UI."""

from typing import Iterable, MutableMapping, NamedTuple, Optional, Dict

from arxiv.submission.domain import Submission
from arxiv.submission.domain.submission import SubmissionContent


class Stage(type):     # type: ignore
    """Stages in the submission UI workflow."""


class BaseStage(metaclass=Stage):
    """Base class for workflow stages."""

    always_check = False
    """If False, the result will be cached when complete."""


def stage_from_endpoint(endpoint: str) -> Stage:
    """Get the :class:`.Stage` for an endpoint."""
    for stage in BaseStage.__subclasses__():
        if stage.endpoint == endpoint:
            return stage
    raise ValueError('No stage for endpoint: %s', endpoint)


class VerifyUser(BaseStage):
    """The user is asked to verify their personal information."""

    endpoint = 'verify_user'
    label = 'verify your personal information'
    title = 'Verify user info'
    display = 'Verify User'

    @staticmethod
    def complete(submission: Submission) -> bool:
        """Determine whether the submitter has verified their information."""
        return submission.submitter_contact_verified is True


class Authorship(BaseStage):
    """The user is asked to verify their authorship status."""

    endpoint = 'authorship'
    label = 'confirm authorship'
    title = "Confirm authorship"
    display = "Authorship"

    @staticmethod
    def complete(submission: Submission) -> bool:
        """Determine whether the submitter has indicated authorship."""
        return submission.submitter_is_author is not None


class License(BaseStage):
    """The user is asked to select a license."""

    endpoint = 'license'
    label = 'choose a license'
    title = "Choose license"
    display = "License"

    @staticmethod
    def complete(submission: Submission) -> bool:
        """Determine whether the submitter has selected a license."""
        return submission.license is not None


class Policy(BaseStage):
    """The user is required to agree to arXiv policies."""

    endpoint = 'policy'
    label = 'accept arXiv submission policies'
    title = "Acknowledge policy"
    display = "Policy"

    @staticmethod
    def complete(submission: Submission) -> bool:
        """Determine whether the submitter has accepted arXiv policies."""
        return submission.submitter_accepts_policy is True


class Classification(BaseStage):
    """The user is asked to select a primary category."""

    endpoint = 'classification'
    label = 'select a primary category'
    title = "Choose category"
    display = "Category"

    @staticmethod
    def complete(submission: Submission) -> bool:
        """Determine whether the submitter selected a primary category."""
        return submission.primary_classification is not None


class CrossList(BaseStage):
    """The user is given the option of selecting cross-list categories."""

    endpoint = 'cross_list'
    label = 'add cross-list categories'
    title = "Add cross-list"
    display = "Cross-list"

    @staticmethod
    def complete(submission: Submission) -> bool:
        return len(submission.secondary_classification) > 0


class FileUpload(BaseStage):
    """The user is asked to upload files for their submission."""

    endpoint = 'file_upload'
    label = 'upload your submission files'
    title = "File upload"
    display = "Upload Files"

    @staticmethod
    def complete(submission: Submission) -> bool:
        """Determine whether the submitter has uploaded files."""
        return submission.source_content is not None


class Process(BaseStage):
    """Uploaded files are processed; this is primarily to compile LaTeX."""

    endpoint = 'file_process'
    label = 'process your submission files'
    title = "File process"
    display = "Process Files"
    always_check = True
    """We need to re-process every time the source is updated."""

    @staticmethod
    def complete(submission: Submission) -> bool:
        """Determine whether the submitter has compiled their upload."""
        # TODO: this might be nice as a property on the submission itself.
        successful = [
            compilation for compilation in submission.compilations
            if compilation.status == compilation.Status.SUCCEEDED
            and compilation.checksum == submission.source_content.checksum
        ]
        return len(successful) > 0 \
            or (submission.source_content
                and submission.source_content.source_format
                is SubmissionContent.Format.PDF)


class Metadata(BaseStage):
    """The user is asked to require core metadata fields, like title."""

    endpoint = 'add_metadata'
    label = 'add required metadata'
    title = "Add metadata"
    display = "Metadata"

    @staticmethod
    def complete(submission: Submission) -> bool:
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
    def complete(submission: Submission) -> bool:
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
    def complete(submission: Submission) -> bool:
        """Determine whether the submission is finalized."""
        return submission.finalized


class Confirm(BaseStage):
    """The submission is confirmed."""

    endpoint = 'confirmation'
    label = 'your submission is confirmed'
    title = "Submission confirmed"
    display = "Confirmed"

    @staticmethod
    def complete(submission: Submission) -> bool:
        return False


class Workflow:

    ORDER = []
    REQUIRED = []
    CONFIRMATION = None

    def __init__(self, submission: Submission,
                 session: MutableMapping) -> None:
        self.submission = submission
        self.session = session

    def __iter__(self):
        """Iterate over stages in this workflow."""
        for stage in self.ORDER:
            yield stage

    def iter_prior(self, stage: Stage) -> Iterable[Stage]:
        """Iterate over stages in this workflow up to a particular stage."""
        for prior_stage in self:
            if prior_stage == stage:
                return
            yield prior_stage

    @property
    def complete(self) -> bool:
        """Determine whether this workflow is complete."""
        return self.submission.finalized

    @property
    def confirmation(self) -> Stage:
        """Get the confirmation :class:`.Stage` for this workflow."""
        return self.CONFIRMATION

    def is_required(self, stage: Stage) -> bool:
        """Check whether a stage is required."""
        return stage in self.REQUIRED

    def next_stage(self, stage: Stage) -> Optional[Stage]:
        """Get the next stage."""
        idx = self.ORDER.index(stage)
        if idx + 1 >= len(self.ORDER):
            return None
        return self.ORDER[idx + 1]

    def previous_stage(self, stage: Stage) -> Optional[Stage]:
        """Get the previous stage."""
        idx = self.ORDER.index(stage)
        if idx == 0:
            return None
        return self.ORDER[idx - 1]

    def can_proceed_to(self, stage: Stage) -> bool:
        """Determine whether the user can proceed to a stage."""
        return self.is_complete(self.previous_stage(stage)) \
            or all(map(self.complete_or_optional, self.iter_prior(stage)))

    def complete_or_optional(self, stage: Stage) -> bool:
        return self.is_complete(stage) or not self.is_required(stage)

    def _get_states(self) -> dict:
        if str(self.submission.submission_id) in self.session:
            states = self.session[str(self.submission.submission_id)]
        else:
            states = {}
        return states

    def _set_states(self, states: dict) -> None:
        self.session[str(self.submission.submission_id)] = states

    @property
    def current_states(self) -> Dict[str, bool]:
        """Get the current state of all stages in the workflow."""
        # Check the client session for state info first.
        states = self._get_states()
        # Completion just means that "we have gotten this far." So if we
        # encounter a complete stage, the previous stages "just are" complete.
        for stage in self.ORDER[::-1]:
            # If the status is not set in the client session, or if the client
            # session shows that the state is incomplete, check the submission
            # itself for a fresh look.
            if stage.endpoint not in states \
                    or not states[stage.endpoint] \
                    or stage.always_check:
                states[stage.endpoint] = stage.complete(self.submission)

            # Mark all previous stages as complete if this stage is complete.
            if states[stage.endpoint]:
                for previous_stage in self.iter_prior(stage):
                    states[previous_stage.endpoint] = True
                break   # Nothing more to do.
        self._set_states(states)
        return states

    def is_complete(self, stage: Optional[Stage]) -> bool:
        """Determine whether or not a stage is complete."""
        if stage is None:
            return True
        return self.current_states[stage.endpoint]

    def mark_complete(self, stage: Stage) -> None:
        """Mark a stage as complete."""
        states = self._get_states()
        states[stage.endpoint] = True
        self._set_states(states)

    @property
    def current_stage(self):
        """Get the first incomplete stage in the workflow."""
        for stage in self:
            if not self.is_complete(stage):
                return stage


class SubmissionWorkflow(Workflow):
    ORDER = [
        VerifyUser,
        Authorship,
        License,
        Policy,
        Classification,
        CrossList,
        FileUpload,
        Process,
        Metadata,
        OptionalMetadata,
        FinalPreview,
        Confirm
    ]
    REQUIRED = [
        VerifyUser,
        Authorship,
        License,
        Policy,
        Classification,
        FileUpload,
        Process,
        Metadata,
        FinalPreview,
        Confirm
    ]
    CONFIRMATION = Confirm


class ReplacementWorkflow(Workflow):
    ORDER = [
        VerifyUser,
        Authorship,
        License,
        Policy,
        FileUpload,
        Process,
        Metadata,
        OptionalMetadata,
        FinalPreview,
        Confirm
    ]
    REQUIRED = [
        VerifyUser,
        Authorship,
        License,
        Policy,
        FileUpload,
        Process,
        Metadata,
        FinalPreview,
        Confirm
    ]
