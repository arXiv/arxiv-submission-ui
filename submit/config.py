"""
Flask configuration.

Docstrings are from the `Flask configuration documentation
<http://flask.pocoo.org/docs/0.12/config/>`_.
"""
import os

ON = 'yes'
OFF = 'no'

DEBUG = os.environ.get('DEBUG') == ON
"""enable/disable debug mode"""

TESTING = os.environ.get('TESTING') == ON
"""enable/disable testing mode"""

PROPAGATE_EXCEPTIONS = \
    True if os.environ.get('PROPAGATE_EXCEPTIONS') == ON else None
"""
explicitly enable or disable the propagation of exceptions. If not set or
explicitly set to None this is implicitly true if either TESTING or DEBUG is
true.
"""

PRESERVE_CONTEXT_ON_EXCEPTION = \
    True if os.environ.get('PRESERVE_CONTEXT_ON_EXCEPTION') == ON else None
"""
By default if the application is in debug mode the request context is not
popped on exceptions to enable debuggers to introspect the data. This can be
disabled by this key. You can also use this setting to force-enable it for non
debug execution which might be useful to debug production applications (but
also very risky).
"""

USE_X_SENDFILE = os.environ.get('USE_X_SENDFILE') == ON
"""Enable/disable x-sendfile"""

LOGGER_NAME = os.environ.get('LOGGER_NAME', 'search')
"""The name of the logger."""

LOGGER_HANDLER_POLICY = os.environ.get('LOGGER_HANDLER_POLICY', 'debug')
"""
the policy of the default logging handler. The default is 'always' which means
that the default logging handler is always active. 'debug' will only activate
logging in debug mode, 'production' will only log in production and 'never'
disables it entirely.
"""

SERVER_NAME = os.environ.get('SEARCH_SERVER_NAME', None)
"""
the name and port number of the server. Required for subdomain support
(e.g.: 'myapp.dev:5000') Note that localhost does not support subdomains so
setting this to 'localhost' does not help. Setting a SERVER_NAME also by
default enables URL generation without a request context but with an
application context.
"""

CLASSIC_DATABASE_URI = os.environ.get('CLASSIC_DATABASE_URI', 'sqlite:///')

JWT_SECRET = os.environ.get('JWT_SECRET', 'foosecret')
SECRET_KEY = os.environ.get('FLASK_SECRET', 'fooflasksecret')
CSRF_SECRET = os.environ.get('FLASK_SECRET', 'csrfbarsecret')

FILE_MANAGER_HOST = os.environ.get('FILE_MANAGER_HOST', 'arxiv.org')
FILE_MANAGER_PORT = os.environ.get('FILE_MANAGER_PORT', '443')
FILE_MANAGER_PROTO = os.environ.get('FILE_MANAGER_PROTO', 'https')
FILE_MANAGER_PATH = os.environ.get('FILE_MANAGER_PATH', '')
FILE_MANAGER_ENDPOINT = os.environ.get(
    'FILE_MANAGER_ENDPOINT',
    f'{FILE_MANAGER_PROTO}://{FILE_MANAGER_HOST}:{FILE_MANAGER_PORT}/{FILE_MANAGER_PATH}'
)
FILE_MANAGER_VERIFY = bool(int(os.environ.get('FILE_MANAGER_VERIFY', '1')))

SESSION_COOKIE_NAME = 'submission_ui_session'

EXTERNAL_URL_SCHEME = os.environ.get('EXTERNAL_URL_SCHEME', 'https')
BASE_SERVER = os.environ.get('BASE_SERVER', 'arxiv.org')

URLS = [
    ("help_license", "/help/license", BASE_SERVER),
    ("help_third_party_submission", "/help/third_party_submission", BASE_SERVER),
    ("help_cross", "/help/cross", BASE_SERVER),
    ("help_submit", "/help/submit", BASE_SERVER),
    ("help_ancillary_files", "/help/ancillary_files", BASE_SERVER),
    ("help_whytex", "/help/faq/whytex", BASE_SERVER),
    ("help_default_packages", "/help/submit_tex#wegotem", BASE_SERVER),
    ("help_submit_tex", "/help/submit_tex", BASE_SERVER),
    ("help_submit_pdf", "/help/submit_pdf", BASE_SERVER),
    ("help_submit_ps", "/help/submit_ps", BASE_SERVER),
    ("help_submit_html", "/help/submit_html", BASE_SERVER),
    ("help_metadata", "/help/prep", BASE_SERVER),
    ("help_jref", "/help/jref", BASE_SERVER),
    ("help_withdraw", "/help/withdraw", BASE_SERVER),
    ("help_endorse", "/help/endorsement", BASE_SERVER)
]
"""
URLs for external services, for use with :func:`flask.url_for`.
This subset of URLs is common only within submit, for now - maybe move to base
if these pages seem relevant to other services.

For details, see :mod:`arxiv.base.urls`.
"""
