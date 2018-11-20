"""Controller for JREF submissions."""

from typing import Tuple, Dict, Any, Optional

from werkzeug import MultiDict
from werkzeug.exceptions import InternalServerError, NotFound

from flask import url_for
from wtforms import BooleanField, RadioField
from wtforms.validators import InputRequired, ValidationError, optional

from arxiv import status
from arxiv.base import logging
from arxiv.forms import csrf
from arxiv.users.domain import Session
import arxiv.submission as events

from ..util import load_submission
from . import util
