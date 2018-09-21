"""Request controllers for the submission UI."""

from .upload import upload_files
from .upload import delete as delete_file
from .upload import delete_all as delete_all_files

from . import create, verify_user, authorship, license, policy, \
    classification, metadata

__all__ = ('verify_user', 'authorship', 'license', 'policy', 'classification',
           'metadata', 'create')
