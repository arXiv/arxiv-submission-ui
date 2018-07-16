# arXiv Submission UI

This is the primary interface for arXiv users to submit e-prints to arXiv.
It is comprised of a Flask application built around the [submission core
events](https://github.com/cul-it/arxiv-submission-core) package.

## Quick start

```bash
$ pipenv install --dev
$ CLASSIC_DATABASE_URI='sqlite:///db.sqlite' LOGLEVEL=10 FLASK_APP=app.py FLASK_DEBUG=1 pipenv run flask run
```

## Generating an auth token

This application uses ``arxiv.users.auth`` to enforce authorization rules
at submission endpoints. To create an auth token for use in development or
testing, you need to:

1. Define a ``arxiv.users.domain.Session`` with the desired characteristics,
   and
2. Use the ``arxiv.users.auth.tokens`` module to generate a token.

Here's an example:

```python
from pytz import timezone
from datetime import timedelta, datetime
from arxiv.users import auth, domain

# Specify the validity period for the session.
start = datetime.now(tz=timezone('US/Eastern'))
end = start + timedelta(seconds=36000)   # Make this as long as you want.

# Create a user with endorsements in astro-ph.CO and .GA.
session = domain.Session(
    session_id='123-session-abc',
    start_time=start, end_time=end,
    user=domain.User(
        user_id='235678',
        email='foo@foo.com',
        username='foouser',
        name=domain.UserFullName("Jane", "Bloggs", "III"),
        profile=domain.UserProfile(
            affiliation="FSU",
            rank=3,
            country="de",
            default_category=domain.Category('astro-ph', 'GA'),
            submission_groups=['grp_physics']
        )
    ),
    authorizations=domain.Authorizations(
        scopes=[auth.scopes.CREATE_SUBMISSION,
                auth.scopes.EDIT_SUBMISSION,
                auth.scopes.VIEW_SUBMISSION],
        endorsements=[domain.Category('astro-ph', 'CO'),
                      domain.Category('astro-ph', 'GA')]
    )
)
secret = 'foosecret'    # Note this secret.

token = auth.tokens.encode(session, secret)
```

The resulting token should look something like:

```
'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzZXNzaW9uX2lkIjoiZm9vaWQiLCJzdGFydF90aW1lIjoiMjAxOC0wNy0xNlQxMDoxNjozMy43NjA3NzMtMDQ6MDAiLCJ1c2VyIjp7InVzZXJuYW1lIjoiZm9vdXNlciIsImVtYWlsIjoiZm9vQGZvby5jb20iLCJ1c2VyX2lkIjoiMjM1Njc4IiwibmFtZSI6bnVsbCwicHJvZmlsZSI6bnVsbH0sImNsaWVudCI6bnVsbCwiZW5kX3RpbWUiOm51bGwsImF1dGhvcml6YXRpb25zIjp7ImNsYXNzaWMiOjAsImVuZG9yc2VtZW50cyI6W10sInNjb3BlcyI6WyJzdWJtaXNzaW9uOnJlYWQiXX0sImlwX2FkZHJlc3MiOm51bGwsInJlbW90ZV9ob3N0IjpudWxsLCJub25jZSI6bnVsbH0.FBMgmyByH7hA-IxwOOGTzZPLtbxE17Q1Wj5RkDBgXt8'
```

You will need to add an ``Authorization`` header to your requests. There are
apps that will do this for you. For Chrome, try [Requestly](https://chrome.google.com/webstore/detail/requestly-redirect-url-mo/mdnleldcmiljblolnjhpnblkcekpdkpa?hl=en)
or [ModHeader](https://chrome.google.com/webstore/detail/modheader/idgpnmonknjnojddfkpgkljpfnnfcklj?hl=en).

Run the application with (note that JWT_SECRET must match above):

```python
JWT_SECRET=foosecret \
    CLASSIC_DATABASE_URI='sqlite:///db.sqlite' \
    LOGLEVEL=10 \
    FLASK_APP=app.py \
    FLASK_DEBUG=1 \
    pipenv run flask run
```


## Code quality

### Linting

[Pylint](https://github.com/PyCQA/pylint) should pass at 9/10 or greater, given
the ``.pylintrc`` config in this repo.

```bash
$ pipenv run pylint submit

Using config file /Users/brp53/projects/arxiv-submission-ui/.pylintrc
************* Module submit.routes.ui
submit/routes/ui.py:9: [W0511(fixme), ] TODO: might be refactored into a series of macros and fewer single-page

-----------------------------------
Your code has been rated at 9.88/10
```

### Code documentation

[Pydocstyle](https://github.com/PyCQA/pydocstyle) should pass without errors,
using [NumPy style
docstrings](http://www.sphinx-doc.org/en/master/ext/example_numpy.html).

```bash
$ pipenv run pydocstyle --convention=numpy --add-ignore=D401
$
```

### Static checking

Use [type annotations](https://docs.python.org/3/library/typing.html)
throughout this project (except in tests). [Mypy](http://mypy-lang.org/) should
pass with no errors or warnings, given the ``mypy.ini`` configuration in this
repo and excluding "defined here" messages.

```
$ pipenv run mypy submit | grep -v "test.*" | grep -v "defined here"
$
```

If mypy complains about something that is verifiably not an error (e.g. a
known limitation of mypy), use inline ``# type: ignore`` comments to suppress
the message. You should also add a comment describing why you're suppressing
the error, including any relevant context (e.g. GitHub issues, SO threads,
etc).
