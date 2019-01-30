# arXiv Submission UI

This is the primary interface for arXiv users to submit e-prints to arXiv.
It is comprised of a Flask application built around the [submission core
events](https://github.com/cul-it/arxiv-submission-core) package.

The Submission UI requires the File Management service.

## Quick start

Start the File Management service.

```bash
$ cd arxiv-filemanager
$ git pull
$ pipenv install --dev
$ LOGLEVEL=10 JWT_SECRET=foosecret LOGLEVEL=10 FLASK_APP=app.py FLASK_DEBUG=1 pipenv run flask run --port=8002
```

```bash
$ cd arxiv-submission-ui
$ # Check out branch you are evaluating and be sure to pull recent changes
$ git pull
$ pipenv install --dev
$ JWT_SECRET=foosecret CLASSIC_DATABASE_URI='sqlite:///db.sqlite' LOGLEVEL=10 FLASK_APP=app.py FLASK_DEBUG=1 pipenv run flask run
```

## Generating an auth token

You MUST create a valid token to run the UI/FM development environment. The easiest way to do this is use the generate_token.py script in arxiv-auth.

```bash
$ cd arxiv-auth
$ git pull
$ pipenv install ./users
$ JWT_SECRET=foosecret pipenv run python generate_token.py
Numeric user ID: 1234
Email address: jdoe@cornell.edu
Username: Jane Doe
First name [Jane]:
Last name [Doe]:
Name suffix [IV]:
Affiliation [Cornell University]:
Numeric rank [3]:
Alpha-2 country code [us]:
Default category [astro-ph.GA]:
Submission groups (comma delim) [grp_physics]:
Endorsement categories (comma delim) [astro-ph.CO,astro-ph.GA]:
Authorization scope (space delim) [public:read submission:create submission:update submission:read upload:create upload:update upload:read upload:delete upload:read_logs]:
eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzZXNzaW9uX2lkIjoiNTI3Yjc1NWMtZTA1Yi00ZWRlLTlmMzEtY2ViMzg4ZjY2NjVkIiwic3RhcnRfdGltZSI6IjIwMTgtMTAtMjNUMTE6MTc6MDkuNDczMzU1LTA0OjAwIiwidXNlciI6eyJ1c2VybmFtZSI6IkRhdmlkIEZyZWRkeSIsImVtYWlsIjoiZGxmMkBjb3JuZWxsLmVkdSIsInVzZXJfaWQiOiIxMjM0IiwibmFtZSI6eyJmb3JlbmFtZSI6IkphbmUiLCJzdXJuYW1lIjoiRG9lIiwic3VmZml4IjoiSVYifSwicHJvZmlsZSI6eyJhZmZpbGlhdGlvbiI6IkNvcm5lbGwgVW5pdmVyc2l0eSIsImNvdW50cnkiOiJ1cyIsInJhbmsiOjMsInN1Ym1pc3Npb25fZ3JvdXBzIjpbImdycF9waHlzaWNzIl0sImRlZmF1bHRfY2F0ZWdvcnkiOnsiYXJjaGl2ZSI6ImFzdHJvLXBoIiwic3ViamVjdCI6IkdBIn0sImhvbWVwYWdlX3VybCI6IiIsInJlbWVtYmVyX21lIjp0cnVlfSwidmVyaWZpZWQiOmZhbHNlfSwiY2xpZW50IjpudWxsLCJlbmRfdGltZSI6IjIwMTgtMTAtMjNUMjE6MTc6MDkuNDczMzU1LTA0OjAwIiwiYXV0aG9yaXphdGlvbnMiOnsiY2xhc3NpYyI6MCwiZW5kb3JzZW1lbnRzIjpbeyJhcmNoaXZlIjoiYXN0cm8tcGgiLCJzdWJqZWN0IjoiQ08ifSx7ImFyY2hpdmUiOiJhc3Ryby1waCIsInN1YmplY3QiOiJHQSJ9XSwic2NvcGVzIjpbeyJkb21haW4iOiJwdWJsaWMiLCJhY3Rpb24iOiJyZWFkIiwicmVzb3VyY2UiOm51bGx9LHsiZG9tYWluIjoic3VibWlzc2lvbiIsImFjdGlvbiI6ImNyZWF0ZSIsInJlc291cmNlIjpudWxsfSx7ImRvbWFpbiI6InN1Ym1pc3Npb24iLCJhY3Rpb24iOiJ1cGRhdGUiLCJyZXNvdXJjZSI6bnVsbH0seyJkb21haW4iOiJzdWJtaXNzaW9uIiwiYWN0aW9uIjoicmVhZCIsInJlc291cmNlIjpudWxsfSx7ImRvbWFpbiI6InVwbG9hZCIsImFjdGlvbiI6ImNyZWF0ZSIsInJlc291cmNlIjpudWxsfSx7ImRvbWFpbiI6InVwbG9hZCIsImFjdGlvbiI6InVwZGF0ZSIsInJlc291cmNlIjpudWxsfSx7ImRvbWFpbiI6InVwbG9hZCIsImFjdGlvbiI6InJlYWQiLCJyZXNvdXJjZSI6bnVsbH0seyJkb21haW4iOiJ1cGxvYWQiLCJhY3Rpb24iOiJkZWxldGUiLCJyZXNvdXJjZSI6bnVsbH0seyJkb21haW4iOiJ1cGxvYWQiLCJhY3Rpb24iOiJyZWFkX2xvZ3MiLCJyZXNvdXJjZSI6bnVsbH1dfSwiaXBfYWRkcmVzcyI6bnVsbCwicmVtb3RlX2hvc3QiOm51bGwsIm5vbmNlIjpudWxsfQ.9-bVljfCz4jwaJLTq1sXhgawlB5H0qrmYtwl60PC4aE
```

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
