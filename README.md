# arXiv Submission UI

This is the primary interface for arXiv users to submit e-prints to arXiv.
It is comprised of a Flask application built around the [submission core
events](https://github.com/cul-it/arxiv-submission-core) package.

The Submission UI requires the File Management service.

## Quick start

Submission involves several back-end services, worker processes and
the UI application itself. The easiest way to spin up all of this
stuff with correct wiring is to use the provided docker-compose
configuration.

### AWS Credentials
First, you will need credentials to AWS ECR to get the converter docker
image. You should only need to do this once. If it seems your quick
start is not running the compiler it is probably because it cannot
access this docker image on AWS ECR.

To do this, 
1. log on to Cornell's AWS single sign-on http://signin.aws.cucloud.net
2. On the AWS console, got to IAM
3. Click "users: on the left, click the button "Add user"
4. Add a name like YOURNETID-dev, click "Programmatic access", click "next: permissions"
5. Click "Copy permissions from existing user", select radio button for "arxiv-ecr-test", Click on the bottom "Next: tags"
6. Click on bottom "next: review", click on bottom "create user", Click "Download.csv"

7. Install awscli, on linux you can do "pip install awscli" or "pipenv install awscli" or look up how to do this on your OS.

8. On the command line run `aws configure` and enter the AWS access key ID, AWS secret access key and region when prompted.

To test if you have access to ECR run:
`aws ecr list-images --repository-name arxiv`
You should get a response of no error and a list of docker images.

### Quick start commands

```bash
cd /path/to/arxiv-submission-ui
mkdir /tmp/foo          # Compiler service will use this.
docker-compose pull     # Pulls in images that you might not have already.
docker-compose build    # Builds the submission UI
DIND_SOURCE_ROOT=/tmp/foo CONVERTER_DOCKER_IMAGE=626657773168.dkr.ecr.us-east-1.amazonaws.com/arxiv/converter:0.9 docker-compose up
```

You may see the following errors when running ``docker-compose pull``,
and you can ignore them:

```bash
ERROR: for mock-classifier  pull access denied for arxiv/mock-classifier, repository does not exist or may require 'docker login'
ERROR: for submission-ui  manifest for arxiv/submission-ui:latest not found
ERROR: for mock-vault  pull access denied for arxiv/mock-vault, repository does not exist or may require 'docker login'
ERROR: for submission-bootstrap  manifest for arxiv/submission-ui:latest not found
ERROR: pull access denied for arxiv/mock-vault, repository does not exist or may require 'docker login'
```

The `DIND_SOURCE_ROOT...docker-compose up` command will start a whole
bunch of stuff. Fairly late in the process, a bootstrap process will
run and generate a bunch of users who are authorized to submit
things. It will look something like this:

```
submission-bootstrap     | 1 picoline2058@gmail.com eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzZXNzaW9uX2lkIjoiYWQyY2UxNmUtMjQwNi00NjgwLWI2NWItMDE3NGYyNDA0MzhlIiwic3RhcnRfdGltZSI6IjIwMTktMDItMTNUMTI6MjM6MzQuMjE2NzcxLTA1OjAwIiwidXNlciI6eyJ1c2VybmFtZSI6InBpY29saW5lMjA1OEBnbWFpbC5jb20iLCJlbWFpbCI6InBpY29saW5lMjA1OEBnbWFpbC5jb20iLCJ1c2VyX2lkIjoxLCJuYW1lIjp7ImZvcmVuYW1lIjoiTWF1cmEiLCJzdXJuYW1lIjoiWmFyZW1iYSIsInN1ZmZpeCI6IlBhbiJ9LCJwcm9maWxlIjp7ImFmZmlsaWF0aW9uIjoiQ29ybmVsbCBVbml2ZXJzaXR5IiwiY291bnRyeSI6InVzIiwicmFuayI6Mywic3VibWlzc2lvbl9ncm91cHMiOlsiZ3JwX3BoeXNpY3MiXSwiZGVmYXVsdF9jYXRlZ29yeSI6ImFzdHJvLXBoLkdBIiwiaG9tZXBhZ2VfdXJsIjoiIiwicmVtZW1iZXJfbWUiOnRydWV9LCJ2ZXJpZmllZCI6ZmFsc2V9LCJjbGllbnQiOm51bGwsImVuZF90aW1lIjoiMjAxOS0wMi0xM1QyMjoyMzozNC4yMTY3NzEtMDU6MDAiLCJhdXRob3JpemF0aW9ucyI6eyJjbGFzc2ljIjowLCJlbmRvcnNlbWVudHMiOlsiKi4qIl0sInNjb3BlcyI6WyJwdWJsaWM6cmVhZCIsInN1Ym1pc3Npb246Y3JlYXRlIiwic3VibWlzc2lvbjp1cGRhdGUiLCJzdWJtaXNzaW9uOnJlYWQiLCJ1cGxvYWQ6cmVhZCIsInVwbG9hZDp1cGRhdGUiLCJ1cGxvYWQ6ZGVsZXRlIiwidXBsb2FkOnJlYWRfbG9ncyJdfSwiaXBfYWRkcmVzcyI6bnVsbCwicmVtb3RlX2hvc3QiOm51bGwsIm5vbmNlIjpudWxsfQ.iNOiCGVIZi5iipElLRyUlnx9uucdK7aytjkvr87FTvI
submission-bootstrap     | 2 aggregat2070@gmail.com eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzZXNzaW9uX2lkIjoiODhmYzMwYTUtNWMyMi00N2ZlLWIzMzEtMDJkNWFhNjUxZjRkIiwic3RhcnRfdGltZSI6IjIwMTktMDItMTNUMTI6MjM6MzQuMjIxNDQ3LTA1OjAwIiwidXNlciI6eyJ1c2VybmFtZSI6ImFnZ3JlZ2F0MjA3MEBnbWFpbC5jb20iLCJlbWFpbCI6ImFnZ3JlZ2F0MjA3MEBnbWFpbC5jb20iLCJ1c2VyX2lkIjoyLCJuYW1lIjp7ImZvcmVuYW1lIjoiQmlsZ2UiLCJzdXJuYW1lIjoiT2t1bXVcdTAxNWYiLCJzdWZmaXgiOiJQcm9mLiJ9LCJwcm9maWxlIjp7ImFmZmlsaWF0aW9uIjoiQ29ybmVsbCBVbml2ZXJzaXR5IiwiY291bnRyeSI6InVzIiwicmFuayI6Mywic3VibWlzc2lvbl9ncm91cHMiOlsiZ3JwX3BoeXNpY3MiXSwiZGVmYXVsdF9jYXRlZ29yeSI6ImFzdHJvLXBoLkdBIiwiaG9tZXBhZ2VfdXJsIjoiIiwicmVtZW1iZXJfbWUiOnRydWV9LCJ2ZXJpZmllZCI6ZmFsc2V9LCJjbGllbnQiOm51bGwsImVuZF90aW1lIjoiMjAxOS0wMi0xM1QyMjoyMzozNC4yMjE0NDctMDU6MDAiLCJhdXRob3JpemF0aW9ucyI6eyJjbGFzc2ljIjowLCJlbmRvcnNlbWVudHMiOlsiKi4qIl0sInNjb3BlcyI6WyJwdWJsaWM6cmVhZCIsInN1Ym1pc3Npb246Y3JlYXRlIiwic3VibWlzc2lvbjp1cGRhdGUiLCJzdWJtaXNzaW9uOnJlYWQiLCJ1cGxvYWQ6cmVhZCIsInVwbG9hZDp1cGRhdGUiLCJ1cGxvYWQ6ZGVsZXRlIiwidXBsb2FkOnJlYWRfbG9ncyJdfSwiaXBfYWRkcmVzcyI6bnVsbCwicmVtb3RlX2hvc3QiOm51bGwsIm5vbmNlIjpudWxsfQ.dZdha4zYX9KYsCCucCxcTNVFQQdV4p-ml00XvKKI2zY
```

Those are some JWTs you can use to access the submission UI. You will need to
pass the JWT in the ``Authorization`` header.

Keep in mind that it can take a little while for everything to spin up -- each
service checks for all of its upstreams to be available, and provisions any
necessary AWS resources (in localstack).

Some of the last things you should see are the submission agent spooling
through some test messages.

```
arxiv-submission-agent    | application 29/May/2019:15:20:24 +0000 - __main__ - None - [arxiv:null] - INFO: "Processing record 49596144802018655118071366264305326833780872579347644418"
arxiv-submission-agent    | application 29/May/2019:15:20:24 +0000 - __main__ - None - [arxiv:null] - INFO: "Skipping record 49596144802018655118071366264305326833780872579347644418"
arxiv-submission-agent    | application 29/May/2019:15:20:24 +0000 - __main__ - None - [arxiv:null] - INFO: "Processing record 49596144802018655118071366264306535759600487208522350594"
arxiv-submission-agent    | application 29/May/2019:15:20:24 +0000 - __main__ - None - [arxiv:null] - INFO: "Skipping record 49596144802018655118071366264306535759600487208522350594"
arxiv-submission-agent    | application 29/May/2019:15:20:24 +0000 - __main__ - None - [arxiv:null] - INFO: "Processing record 49596144802018655118071366264307744685420103555683975170"
arxiv-submission-agent    | application 29/May/2019:15:20:24 +0000 - __main__ - None - [arxiv:null] - INFO: "Skipping record 49596144802018655118071366264307744685420103555683975170"
arxiv-submission-agent    | application 29/May/2019:15:20:24 +0000 - __main__ - None - [arxiv:null] - INFO: "Processing record 49596144802018655118071366264308953611239718184858681346"
arxiv-submission-agent    | application 29/May/2019:15:20:24 +0000 - __main__ - None - [arxiv:null] - INFO: "Skipping record 49596144802018655118071366264308953611239718184858681346"
```

You should be able to access the UI at http://localhost:8000. If you don't
get a response right away, the UI is probably still waiting for something
to come up.

### Rerunning the quick start

To get a fresh deployment (e.g. after significant changes to backend
stuff), you may need to blow away the whole service group. Be sure to
use the ``-v`` flag to drop old volumes.

```bash
docker-compose rm -v
```

## Running the UI locally

In addition, the compose config maps ports for backend services and data
stores to your local machine. So you can also start the UI via the Flask
development server for quicker cycles.

| Service      | Env var                   | Endpoint                                                                  |
|--------------|---------------------------|---------------------------------------------------------------------------|
| File manager | ``FILEMANAGER_ENDPOINT`` | http://localhost:8001/filemanager/api                                     |
| Compiler     | ``COMPILER_ENDPOINT``     | http://localhost:8100/                                                    |
| Redis        | ``SUBMISSION_BROKER_URL`` | redis://localhost:6380                                                    |
| Legacy DB    | ``CLASSIC_DATABASE_URI``  | mysql+mysqldb://foouser:foopass@127.0.0.1:3307/submission?charset=utf8mb4 |


So you can start the submission UI in dev mode with something like:

```bash
$ cd arxiv-submission-ui
$ # Check out branch you are evaluating and be sure to pull recent changes
$ git pull
$ pipenv install --dev
$ export VAULT_ENABLED="0"
$ export NAMESPACE="development"
$ export LOGLEVEL=10
$ export JWT_SECRET=foosecret
$ export SESSION_COOKIE_SECURE=0
$ export CLASSIC_DATABASE_URI="mysql+mysqldb://foouser:foopass@127.0.0.1:3307/submission?charset=utf8mb4"
$ export WAIT_FOR_SERVICES=0
$ export WAIT_ON_STARTUP=0
$ export FILEMANAGER_ENDPOINT="http://localhost:8001/filemanager/api"
$ export FILEMANAGER_CONTENT_PATH="/{source_id}/content"
$ export COMPILER_ENDPOINT="http://localhost:8100/"
$ export COMPILER_VERIFY=0
$ export PREVIEW_ENDPOINT='http://localhost:9001/'
$ export PREVIEW_VERIFY=0
$ export KINESIS_STREAM="SubmissionEvents"
$ export KINESIS_VERIFY=0
$ export KINESIS_ENDPOINT="https://localhost:4568"
$ export KINESIS_START_TYPE="TRIM_HORIZON"
$ FLASK_APP=app.py FLASK_DEBUG=1 pipenv run flask run
```

And access it at http://localhost:5000.

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
            default_category=domain.Category('astro-ph.GA'),
            submission_groups=['grp_physics']
        )
    ),
    authorizations=domain.Authorizations(
        scopes=[auth.scopes.CREATE_SUBMISSION,
                auth.scopes.EDIT_SUBMISSION,
                auth.scopes.VIEW_SUBMISSION],
        endorsements=[domain.Category('astro-ph.CO'),
                      domain.Category('astro-ph.GA')]
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
