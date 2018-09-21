"""Core data concepts in the submission UI application."""

from typing import NamedTuple, List, Optional
from datetime import datetime
import dateutil.parser

from arxiv.submission.domain import Submission


class SubmissionStage(NamedTuple):
    """Represents the furthest completed stage reached by a submission."""

    submission: Submission

    def user_is_verified(self) -> bool:
        """Determine whether the submitter has verified their information."""
        return self.submission.submitter_contact_verified

    def authorship_is_set(self) -> bool:
        """Determine whether the submitter has indicated authorship."""
        return self.submission.submitter_is_author is not None

    def license_is_set(self) -> bool:
        """Determine whether the submitter has selected a license."""
        return self.submission.license is not None

    def policy_is_accepted(self) -> bool:
        """Determine whether the submitter has accepted arXiv policies."""
        return self.submission.submitter_accepts_policy is True

    def classification_is_set(self) -> bool:
        """Determine whether the submitter selected a primary category."""
        return self.submission.primary_classification is not None

    def files_are_uploaded(self) -> bool:
        """Determine whether the submitter has uploaded files."""
        return self.submission.source_content is not None

    def files_are_processed(self) -> bool:
        """Determine whether the submitter has compiled their upload."""
        return len(self.submission.compiled_content) > 0

    def metadata_is_set(self) -> bool:
        """Determine whether the submitter has entered required metadata."""
        return (self.submission.metadata.title is not None
                and self.submission.metadata.abstract is not None
                and self.submission.metadata.authors_display is not None)

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
    """The user is given the option of entering optional metadata, like DOI."""
    FINAL_PREVIEW = 'final_preview'
    """The user is asked to review the submission before finalizing."""

    LABELS = {
        VERIFY_USER: 'verify your personal information',
        AUTHORSHIP: 'confirm authorship',
        LICENSE: 'choose a license',
        POLICY: 'accept arXiv submission policies',
        CLASSIFICATION: 'select a primary category',
        CROSS_LIST: 'add cross-list categories',
        FILE_UPLOAD: 'upload your submission files',
        FILE_PROCESS: 'process your submission files',
        ADD_METADATA: 'add required metadata',
        ADD_OPTIONAL_METADATA: 'add optional metadata',
        FINAL_PREVIEW: 'preview and approve your submission'
    }
    """
    Human-intelligible labels for the submission steps.

    These can be used in templates to convey what the user is being asked to
    do.
    """

    ORDER = [
        (VERIFY_USER, True, user_is_verified),
        (AUTHORSHIP, True, authorship_is_set),
        (LICENSE, True, license_is_set),
        (POLICY, True, policy_is_accepted),
        (CLASSIFICATION, True, classification_is_set),
        (CROSS_LIST, False, None),
        (FILE_UPLOAD, True, files_are_uploaded),
        (FILE_PROCESS, True, files_are_processed),
        (ADD_METADATA, True, metadata_is_set),
        (ADD_OPTIONAL_METADATA, False, None),
        (FINAL_PREVIEW, True, None)
    ]
    """
    The standard order for submission steps.

    Within each 3-tuple, the accompanying bool indicates whether that step is
    required, and the subsequent instance method can be used to verify that
    the step has been completed.
    """

    @property
    def current_stage(self) -> Optional[str]:
        """
        The current stage of the submission.

        This is the furthest stage that the user has completed in the
        submission process.
        """
        previous = None
        for i, (stage, required, method) in enumerate(self.ORDER):
            if not required:    # Will skip over optional steps.
                continue
            if method and not method(self):
                return previous
            previous = stage
        return None

    @property
    def previous_stage(self) -> str:
        """The previous stage in the submission process for this submission."""
        return self.get_previous_stage(self.current_stage)

    @property
    def previous_required_stage(self) -> str:
        """The previous required stage in the submission process."""
        previous = self.get_previous_stage(self.current_stage)
        while not self.is_required(previous):
            previous = self.get_previous_stage(previous)
        return previous

    @property
    def next_required_stage(self) -> str:
        """The next required stage in the submission process."""
        next_stage = self.get_next_stage(self.current_stage)
        while not self.is_required(next_stage):
            next_stage = self.get_next_stage(next_stage)
        return next_stage

    @property
    def next_stage(self) -> str:
        """The next stage of the submission process."""
        return self.get_next_stage(self.current_stage)

    def can_proceed_to(self, stage: str) -> bool:
        """Determine whether the user can proceed to a particular stage."""
        previous: Optional[str] = self.get_previous_stage(stage)
        if previous is None:
            return True
        return self.has_completed(previous)

    def get_next_stage(self, stage: str) -> str:
        """Get the next stage in the submission process for this submission."""
        if stage is None:     # No stage achieved; start at the beginning.
            return self.ORDER[0][0]

        stages = self._get_stage_list()
        if self._get_index(stage) == len(stages) - 1:
            return None     # Last stage is complete; naught to do.
        # Get the stage after the current stage.
        return stages[self._get_index(stage) + 1]

    def get_previous_stage(self, stage: str) -> str:
        """Get the previous stage in the submission process."""
        stages = self._get_stage_list()
        if stage is None:   # There is nothing before nothing.
            return None
        if self._get_index(stage) == 0:    # This is already the first stage.
            return None
        # Get the stage before the current stage.
        return stages[self._get_index(stage) - 1]

    def _get_stage_list(self) -> List[str]:
        stages, _, _ = zip(*self.ORDER)
        return list(stages)

    def _get_current_index(self) -> int:
        if self.current_stage is None:
            return -1
        return self._get_index(self.current_stage)

    def _get_index(self, stage: str) -> int:
        if stage is None:
            return -1
        return self._get_stage_list().index(stage)

    def before(self, stage: str) -> bool:
        """Less-than comparator."""
        return self._get_current_index() < self._get_index(stage)

    def on_or_before(self, stage: str) -> bool:
        """Less-than or equal-to comparator."""
        return self._get_current_index() <= self._get_index(stage)

    def after(self, stage: str) -> bool:
        """Greater-than comparator."""
        return self._get_current_index() > self._get_index(stage)

    def on_or_after(self, stage: str) -> bool:
        """Greater-than or equal-to comparator."""
        return self._get_current_index() >= self._get_index(stage)

    def has_completed(self, stage: str) -> bool:
        """Determine whether a stage has been completed."""
        i = self._get_index(stage)
        _, required, method = self.ORDER[i]
        if method:
            return method(self)
        elif not required:
            if i == 0:
                return True
            x = i
            _required = False
            while not _required and x > 0:
                x -= 1
                _, _required, method = self.ORDER[x]
            if method:
                return method(self)
        return False

    def is_required(self, stage: str) -> bool:
        """Determine whether or not a stage is required."""
        stages, required, _ = zip(*self.ORDER)
        return dict(zip(stages, required))[stage]


class FileError(NamedTuple):
    """Represents an error returned by the file management service."""

    ERROR = 'ERROR'
    WARNING = 'WARN'

    error_type: str
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
    def from_dict(cls: type, data: dict) -> 'Error':
        """Instantiate a :class:`FileError` from a dict."""
        return cls(**data)


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
            'modified': self.modified,
            'ancillary': self.ancillary,
            'errors': self.errors
        }
        if data['modified']:
            data['modified'] = data['modified'].isoformat()
        if data['errors']:
            data['errors'] = [e.to_dict() for e in data['errors']]
        return data

    @classmethod
    def from_dict(cls: type, data: dict) -> 'UploadStatus':
        """Instantiate a :class:`FileStatus` from a dict."""
        if 'errors' in data:
            data['errors'] = [FileError.from_dict(e) for e in data['errors']]
        if 'modified' in data and type(data['modified']) is str:
            data['modified'] = dateutil.parser.parse(data['modified'])
        return cls(**data)


class UploadStatus(NamedTuple):
    """Represents the state of an upload workspace."""

    READY = 'READY'
    READY_WITH_WARNINGS = 'READY_WITH_WARNINGS'
    ERRORS = 'ERRORS'
    UPLOAD_STATUSES = (READY, READY_WITH_WARNINGS, ERRORS)

    LOCKED = 'LOCKED'
    UNLOCKED = 'UNLOCKED'
    LOCK_STATES = (LOCKED, UNLOCKED)

    ACTIVE = 'ACTIVE'
    RELEASED = 'RELEASED'
    DELETED = 'DELETED'
    WORKSPACE_STATES = (ACTIVE, RELEASED, DELETED)

    started: datetime
    completed: datetime
    created: datetime
    modified: datetime
    status: str
    workspace_state: str
    lock_state: str
    identifier: int
    checksum: Optional[str] = None
    size: Optional[int] = None
    files: List[FileStatus] = []
    errors: List[FileError] = []

    @property
    def locked(self) -> bool:
        """Indicate whether the upload workspace is locked."""
        return self.lock_state == self.LOCKED

    @property
    def file_count(self) -> int:
        """The number of files in the workspace."""
        return len(self.files)

    def to_dict(self) -> dict:
        """Generate a dict representation of this status object."""
        data = {
            'started': self.started,
            'completed': self.completed,
            'created': self.created,
            'modified': self.modified,
            'status': self.status,
            'workspace_state': self.workspace_state,
            'lock_state': self.lock_state,
            'identifier': self.identifier,
            'checksum': self.checksum,
            'size': self.size,
            'files': self.files,
            'errors': self.errors
        }
        for key in ['started', 'completed', 'created', 'modified']:
            if data[key]:
                data[key] = data[key].isoformat()
        if data['files']:
            data['files'] = [d.to_dict() for d in data['files']]
        if data['errors']:
            data['errors'] = [d.to_dict() for d in data['errors']]
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
        return cls(**data)
