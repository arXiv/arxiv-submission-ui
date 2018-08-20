"""Request controllers for the submission UI."""

from .verify_user import verify_user
from .authorship import authorship
from .license import license
from .policy import policy
from .classification import classification, cross_list
from .metadata import metadata, optional
from .create import create
from .upload import upload
from .upload import delete as delete_file

__all__ = ('verify_user', 'authorship', 'license', 'policy', 'classification',
           'cross_list', 'metadata', 'optional', 'create')
