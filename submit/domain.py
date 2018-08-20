from typing import NamedTuple, List, Optional
from datetime import datetime


class Error(NamedTuple):
    ERROR = 'ERROR'
    WARNING = 'WARN'

    error_type: str
    message: str
    more_info: str


class FileStatus(NamedTuple):
    path: str
    name: str
    file_type: str
    size: int
    ancillary: bool = False
    added: Optional[datetime] = None
    errors: List[Error] = []


class UploadStatus(NamedTuple):

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
    errors: List[Error] = []

    @property
    def locked(self) -> bool:
        return self.lock_state == self.LOCKED
