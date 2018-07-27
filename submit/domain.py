from typing import NamedTuple, List
from datetime import datetime


class Error(NamedTuple):
    ERROR = 'ERROR'
    WARNING = 'WARN'

    type: str
    message: str
    more_info: str


class FileStatus(NamedTuple):
    path: str
    name: str
    file_type: str
    added: datetime
    size: int
    ancillary: bool = False
    errors: List[Error] = []


class UploadStatus(NamedTuple):
    identifier: str
    checksum: str
    size: int
    file_list: List[FileStatus] = []
    errors: List[Error] = []
