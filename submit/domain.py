"""Core data concepts in the submission UI application."""

from typing import NamedTuple, List, Optional, Dict
import io
from datetime import datetime
import dateutil.parser
from enum import Enum
import io

from arxiv.submission.domain import Submission


class Stages(Enum):     # type: ignore
    """Stages in the submission UI workflow."""

    VERIFY_USER = 'verify_user'
    """The user is asked to verify their personal information."""
    AUTHORSHIP = 'authorship'
    """The user is asked to verify their authorship status."""
    LICENSE = 'license'
    """The user is asked to select a license."""
    POLICY = 'policy'
    """The user is required to agree to arXiv policies."""
    CLASSIFICATION = 'classification'
    """The user is asked to select a primary category."""
    CROSS_LIST = 'cross_list'
    """The user is given the option of selecting cross-list categories."""
    FILE_UPLOAD = 'file_upload'
    """The user is asked to upload files for their submission."""
    FILE_PROCESS = 'file_process'
    """Uploaded files are processed; this is primarily to compile LaTeX."""
    ADD_METADATA = 'add_metadata'
    """The user is asked to require core metadata fields, like title."""
    ADD_OPTIONAL_METADATA = 'add_optional_metadata'
    """The user is given the option of entering optional metadata."""
    FINAL_PREVIEW = 'final_preview'
    """The user is asked to review the submission before finalizing."""


class StageBase(NamedTuple):
    """Base class for submission stage representation."""

    submission: Submission

    ORDER = []

    LABELS = {
        Stages.VERIFY_USER.value: 'verify your personal information',
        Stages.AUTHORSHIP.value: 'confirm authorship',
        Stages.LICENSE.value: 'choose a license',
        Stages.POLICY.value: 'accept arXiv submission policies',
        Stages.CLASSIFICATION.value: 'select a primary category',
        Stages.CROSS_LIST.value: 'add cross-list categories',
        Stages.FILE_UPLOAD.value: 'upload your submission files',
        Stages.FILE_PROCESS.value: 'process your submission files',
        Stages.ADD_METADATA.value: 'add required metadata',
        Stages.ADD_OPTIONAL_METADATA.value: 'add optional metadata',
        Stages.FINAL_PREVIEW.value: 'preview and approve your submission'
    }
    """
    Human-intelligible labels for the submission steps.

    These can be used in templates to convey what the user is being asked to
    do.
    """

    @staticmethod
    def user_is_verified(submission: Submission) -> bool:
        """Determine whether the submitter has verified their information."""
        return submission.submitter_contact_verified is True

    @staticmethod
    def authorship_is_set(submission: Submission) -> bool:
        """Determine whether the submitter has indicated authorship."""
        return submission.submitter_is_author is not None

    @staticmethod
    def license_is_set(submission: Submission) -> bool:
        """Determine whether the submitter has selected a license."""
        return submission.license is not None

    @staticmethod
    def policy_is_accepted(submission: Submission) -> bool:
        """Determine whether the submitter has accepted arXiv policies."""
        return submission.submitter_accepts_policy is True

    @staticmethod
    def classification_is_set(submission: Submission) -> bool:
        """Determine whether the submitter selected a primary category."""
        return submission.primary_classification is not None

    @staticmethod
    def files_are_uploaded(submission: Submission) -> bool:
        """Determine whether the submitter has uploaded files."""
        return submission.source_content is not None

    @staticmethod
    def files_are_processed(submission: Submission) -> bool:
        """Determine whether the submitter has compiled their upload."""
        return len(submission.compiled_content) > 0

    @staticmethod
    def metadata_is_set(submission: Submission) -> bool:
        """Determine whether the submitter has entered required metadata."""
        return (submission.metadata.title is not None
                and submission.metadata.abstract is not None
                and submission.metadata.authors_display is not None)

    @staticmethod
    def crosslist_is_selected(submission: Submission) -> bool:
        """Determine whether a cross-list category has been selected."""
        return len(submission.secondary_classification) > 0

    @staticmethod
    def optional_metadata_is_set(submission: Submission) -> bool:
        """Determine whether the user has set optional metadata fields."""
        return (submission.metadata.doi is not None
                or submission.metadata.msc_class is not None
                or submission.metadata.acm_class is not None
                or submission.metadata.report_num is not None
                or submission.metadata.journal_ref is not None)

    @classmethod
    def is_relevant(self, stage: Stages) -> bool:
        return stage in tuple(zip(*self.ORDER))[0]

    @property
    def current_stage(self) -> Optional[Stages]:
        """
        The current stage of the submission.

        This is the furthest stage that the user has completed in the
        submission process.
        """
        previous = None
        for i, (stage, required, method) in enumerate(self.ORDER):
            print(stage, required, method)
            if not required:    # Will skip over optional steps.
                print('skip: not required')
                continue
            if method and not method(self.submission):
                print('not complete, return previous')
                return previous
            previous = stage
        return None

    @property
    def previous_stage(self) -> Optional[Stages]:
        """The previous stage in the submission process for this submission."""
        return self.get_previous_stage(self.current_stage)

    @property
    def previous_required_stage(self) -> Optional[Stages]:
        """The previous required stage in the submission process."""
        previous = self.get_previous_stage(self.current_stage)
        while previous is not None and not self.is_required(previous):
            previous = self.get_previous_stage(previous)
        return previous

    @property
    def next_required_stage(self) -> Optional[Stages]:
        """The next required stage in the submission process."""
        next_stage = self.get_next_stage(self.current_stage)
        while next_stage is not None and not self.is_required(next_stage):
            next_stage = self.get_next_stage(next_stage)
        return next_stage

    @property
    def next_stage(self) -> Optional[Stages]:
        """The next stage of the submission process."""
        return self.get_next_stage(self.current_stage)

    def can_proceed_to(self, stage: Optional[Stages]) -> bool:
        """Determine whether the user can proceed to a particular stage."""
        previous = self.get_previous_stage(stage)
        if previous is None:
            return True
        while not self.is_required(previous) and previous is not None:
            previous = self.get_previous_stage(previous)
        return self.has_completed(previous)

    def get_next_stage(self, stage: Optional[Stages]) -> Optional[Stages]:
        """Get the next stage in the submission process for this submission."""
        if stage is None:     # No stage achieved; start at the beginning.
            next_stage: Stages = self.ORDER[0][0]
            return next_stage

        stages = self._get_stage_list()
        if self._get_index(stage) == len(stages) - 1:
            return None     # Last stage is complete; naught to do.
        # Get the stage after the current stage.
        next_stage = stages[self._get_index(stage) + 1]
        return next_stage

    def get_previous_stage(self, stage: Optional[Stages]) -> Optional[Stages]:
        """Get the previous stage in the submission process."""
        stages = self._get_stage_list()
        if stage is None:   # There is nothing before nothing.
            return None
        if self._get_index(stage) == 0:    # This is already the first stage.
            return None
        # Get the stage before the current stage.
        return stages[self._get_index(stage) - 1]

    def _get_stage_list(self) -> List[Stages]:
        stages, _, _ = zip(*self.ORDER)
        return list(stages)

    def _get_current_index(self) -> int:
        if self.current_stage is None:
            return -1
        return self._get_index(self.current_stage)

    def _get_index(self, stage: Stages) -> int:
        if stage is None:
            return -1
        return self._get_stage_list().index(stage)

    def before(self, stage: Stages) -> bool:
        """Less-than comparator."""
        return self._get_current_index() < self._get_index(stage)

    def on_or_before(self, stage: Stages) -> bool:
        """Less-than or equal-to comparator."""
        return self._get_current_index() <= self._get_index(stage)

    def after(self, stage: Stages) -> bool:
        """Greater-than comparator."""
        return self._get_current_index() > self._get_index(stage)

    def on_or_after(self, stage: Stages) -> bool:
        """Greater-than or equal-to comparator."""
        return self._get_current_index() >= self._get_index(stage)

    def is_on_or_after(self, stage_a: Stages, stage_b: Stages) -> bool:
        """Determine whether stage_a is equivalent to or after stage_b."""
        return self._get_index(stage_a) >= self._get_index(stage_b)

    def has_completed(self, stage: Stages) -> bool:
        """Determine whether a stage has been completed."""
        i = self._get_index(stage)
        _, required, method = self.ORDER[i]

        if method:
            return bool(method(self.submission))
        return False

    def is_required(self, stage: Stages) -> bool:
        """Determine whether or not a stage is required."""
        stages, required, _ = zip(*self.ORDER)
        return bool(dict(zip(stages, required))[stage])


# TODO: many of the instance methods on this class could be classmethods
#  or staticmethods.
class SubmissionStage(StageBase):
    """Represents the furthest completed stage reached by a submission."""

    Stages = Stages

    ORDER = [
        (Stages.VERIFY_USER, True, StageBase.user_is_verified),
        (Stages.AUTHORSHIP, True, StageBase.authorship_is_set),
        (Stages.LICENSE, True, StageBase.license_is_set),
        (Stages.POLICY, True, StageBase.policy_is_accepted),
        (Stages.CLASSIFICATION, True, StageBase.classification_is_set),
        (Stages.CROSS_LIST, False, StageBase.crosslist_is_selected),
        (Stages.FILE_UPLOAD, True, StageBase.files_are_uploaded),
        (Stages.FILE_PROCESS, True, StageBase.files_are_processed),
        (Stages.ADD_METADATA, True, StageBase.metadata_is_set),
        (Stages.ADD_OPTIONAL_METADATA, StageBase.optional_metadata_is_set, None),
        (Stages.FINAL_PREVIEW, True, None)
    ]
    """
    The standard order for submission steps.

    Within each 3-tuple, the accompanying bool indicates whether that step is
    required, and the subsequent instance method can be used to verify that
    the step has been completed.
    """


class ReplacementStage(StageBase):
    """Represents the furthest completed stage reached by a replacement."""

    Stages = Stages

    ORDER = [
        (Stages.VERIFY_USER, True, StageBase.user_is_verified),
        (Stages.AUTHORSHIP, True, StageBase.authorship_is_set),
        (Stages.LICENSE, True, StageBase.license_is_set),
        (Stages.POLICY, True, StageBase.policy_is_accepted),
        (Stages.FILE_UPLOAD, True, StageBase.files_are_uploaded),
        (Stages.FILE_PROCESS, True, StageBase.files_are_processed),
        (Stages.ADD_METADATA, True, StageBase.metadata_is_set),
        (Stages.ADD_OPTIONAL_METADATA, StageBase.optional_metadata_is_set, None),
        (Stages.FINAL_PREVIEW, True, None)
    ]
    """
    The standard order for replacement steps.

    Within each 3-tuple, the accompanying bool indicates whether that step is
    required, and the subsequent instance method can be used to verify that
    the step has been completed.
    """


class FileError(NamedTuple):
    """Represents an error returned by the file management service."""

    class Levels(Enum):   # type: ignore
        """Error severities."""

        ERROR = 'ERROR'
        WARNING = 'WARN'

    error_type: 'FileError.Levels'
    message: str
    more_info: Optional[str] = None

    def to_dict(self) -> dict:
        """Generate a dict representation of this error."""
        return {
            'error_type': self.error_type,
            'message': self.message,
            'more_info': self.more_info
        }

    @classmethod
    def from_dict(cls: type, data: dict) -> 'FileError':
        """Instantiate a :class:`FileError` from a dict."""
        instance: FileError = cls(**data)
        return instance


class FileStatus(NamedTuple):
    """Represents the state of an uploaded file."""

    path: str
    name: str
    file_type: str
    size: int
    modified: datetime
    ancillary: bool = False
    errors: List[FileError] = []

    def to_dict(self) -> dict:
        """Generate a dict representation of this status object."""
        data = {
            'path': self.path,
            'name': self.name,
            'file_type': self.file_type,
            'size': self.size,
            'modified': self.modified.isoformat(),
            'ancillary': self.ancillary,
            'errors': [e.to_dict() for e in self.errors]
        }
        # if data['modified']:
        #     data['modified'] = data['modified']
        # if data['errors']:
        #     data['errors'] = [e.to_dict() for e in data['errors']]
        return data

    @classmethod
    def from_dict(cls: type, data: dict) -> 'UploadStatus':
        """Instantiate a :class:`FileStatus` from a dict."""
        if 'errors' in data:
            data['errors'] = [FileError.from_dict(e) for e in data['errors']]
        if 'modified' in data and type(data['modified']) is str:
            data['modified'] = dateutil.parser.parse(data['modified'])
        instance: UploadStatus = cls(**data)
        return instance


class UploadStatus(NamedTuple):
    """Represents the state of an upload workspace."""

    class Statuses(Enum):   # type: ignore
        """The status of the upload workspace with respect to submission."""

        READY = 'READY'
        READY_WITH_WARNINGS = 'READY_WITH_WARNINGS'
        ERRORS = 'ERRORS'

    class LifecycleStates(Enum):   # type: ignore
        """The status of the workspace with respect to its lifecycle."""

        ACTIVE = 'ACTIVE'
        RELEASED = 'RELEASED'
        DELETED = 'DELETED'

    started: datetime
    completed: datetime
    created: datetime
    modified: datetime
    status: 'UploadStatus.Statuses'
    lifecycle: 'UploadStatus.LifecycleStates'
    locked: bool
    identifier: int
    checksum: Optional[str] = None
    size: Optional[int] = None
    files: List[FileStatus] = []
    errors: List[FileError] = []

    @property
    def file_count(self) -> int:
        """The number of files in the workspace."""
        return len(self.files)

    def to_dict(self) -> dict:
        """Generate a dict representation of this status object."""
        data = {
            'started': self.started.isoformat(),
            'completed': self.completed.isoformat(),
            'created': self.created.isoformat(),
            'modified': self.modified.isoformat(),
            'status': self.status,
            'lifecycle': self.lifecycle,
            'locked': self.locked,
            'identifier': self.identifier,
            'checksum': self.checksum,
            'size': self.size,
            'files': [d.to_dict() for d in self.files],
            'errors': [d.to_dict() for d in self.errors]
        }
        # for key in ['started', 'completed', 'created', 'modified']:
        #     if data[key]:
        #         data[key] = data[key]
        # if data['files']:
        #     data['files'] = [d.to_dict() for d in data['files']]
        # if data['errors']:
        #     data['errors'] = [d.to_dict() for d in data['errors']]
        return data

    @classmethod
    def from_dict(cls: type, data: dict) -> 'UploadStatus':
        """Instantiate an :class:`UploadStatus` from a dict."""
        if 'files' in data:
            data['files'] = [FileStatus.from_dict(f) for f in data['files']]
        if 'errors' in data:
            data['errors'] = [FileError.from_dict(e) for e in data['errors']]
        for key in ['started', 'completed', 'created', 'modified']:
            if key in data and type(data[key]) is str:
                data[key] = dateutil.parser.parse(data[key])
        instance: UploadStatus = cls(**data)
        return instance


class CompilationStatus(NamedTuple):
    """Represents the state of a compilation product in the store."""

    # This is intended as a fixed class attributes, not a slot.
    class Statuses(Enum):      # type: ignore
        COMPLETED = "completed"
        IN_PROGRESS = "in_progress"
        FAILED = "failed"

    # Here are the actual slots/fields.
    upload_id: str

    status: 'CompilationStatus.Statuses'
    """
    The status of the compilation.

    One of :attr:`COMPLETED`, :attr:`IN_PROGRESS`, or :attr:`FAILED`.

    If :attr:`COMPLETED`, the current file corresponding to the format of this
    compilation status is the product of this compilation.
    """

    task_id: Optional[str] = None
    """If a task exists for this compilation, the unique task ID."""

    @property
    def content_type(self):
        _ctypes = {
            CompilationStatus.Formats.PDF: 'application/pdf',
            CompilationStatus.Formats.DVI: 'application/x-dvi',
            CompilationStatus.Formats.PS: 'application/postscript'
        }
        return _ctypes[self.format]

    def to_dict(self) -> dict:
        """Generate a dict representation of this object."""
        return {
            'upload_id': self.upload_id,
            'format': self.format.value,
            'source_checksum': self.source_checksum,
            'task_id': self.task_id,
            'status': self.status.value
        }


class CompilationProduct(NamedTuple):
    """Content of a compilation product itself."""

    stream: io.BytesIO
    """Readable buffer with the product content."""

    status: Optional[CompilationStatus] = None
    """Status information about the product."""

    checksum: Optional[str] = None
    """The B64-encoded MD5 hash of the compilation product."""
