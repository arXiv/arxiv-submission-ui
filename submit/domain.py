from typing import NamedTuple, List, Optional
from datetime import datetime
import dateutil.parser


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
