# arXiv Submission UI

This is the primary interface for arXiv users to submit e-prints to arXiv.
It is comprised of a Flask application built around the [submission core
events](https://github.com/cul-it/arxiv-submission-core) package.

The Submission UI requires the File Management service and optionally requires
the Compiler service when working with articles that must be compiled from TeX
sources. The Compiler service is not required when working with PDF-only submissions.

The Compiler service's converter image currently includes the complete set of all arXiv TeX
trees used by arXiv over the years. This image is rather large (17G) and takes
more effort to download and install so we supply a mock compiler service for cases
where you are not focused on the compilation aspects of the 'process' step within the
submission workflow.

## Overview of Quick start options - full TeX compilation or mock compilation

Submission involves several back-end services, worker processes and
the UI application itself. The easiest way to spin up all of this
stuff with correct wiring is to use the provided docker-compose
configuration.

The default docker-compose configuration requires the fully-functional Compiler
service converter image. To bypass installation of this compiler image use the mock compiler
configuration option.

How to chose the option that's right for you: If you are not concerned with TeX
compilation, or you have limited disk space, you will want the mock compiler option.
If you are concerned with evaluating TeX compilation output and/or the submission
'process' step under normal operating conditions you will want to install the
actual Compiler service's converter image.

## Setup required for both mock and full compilation options - AWS settings

One of the back-end services we run is 'localstack' which is a fully functional
local AWS stack. While this local AWS stack implementation doesn't actually
check credentials you must have the environment variables set for the service
to work properly.

You may set these to your real AWS credentials or simply set them to arbitrary
dummy values.

```bash
export AWS_ACCESS_KEY_ID=fookey
export AWS_SECRET_ACCESS_KEY=foosecretkey
```

## Quick start using mock compiler service

The mock compiler service simulates responses from the compilation service. The primary
deliverables of the compiler service are the PDF and logs generated from compiling the submission's
TeX source. The mock compiler service simply returns a fixed PDF and compilation log.

Use the 'docker-compose-mock-compiler.yml' configuration file to enable the mock compiler
service. You will need to add the '-f <config file>' argument to all docker-compose commands.
Another option is to replace the 'docker-compose.yml' with the 'docker-compose-mock-compiler.yml'
in the event you do not want to bother with adding the '-f' argument. Be careful not to commit this
overwrite of the default configuration file.

### Quick start commands (mock compiler)

Make sure you have your AWS settings configured properly before proceeding ([see above](#aws-credentials)).

docker-compose note: When you are running with an alternate config (-f <config>) you will want to add
the '-f <config>' argument to all docker-compose commands since this configuration file defines the set of services
it is operating on.

```bash
cd /path/to/arxiv-submission-ui
mkdir /tmp/foo          # Compiler service will use this.
docker-compose -f docker-compose-mock-compiler.yml pull     # Pulls in images that you might not have already.
docker-compose -f docker-compose-mock-compiler.yml build    # Builds the submission UI
DIND_SOURCE_ROOT=/tmp/foo docker-compose -f docker-compose-mock-compiler.yml up
```

You may see the following errors when running ``docker-compose -f docker-compose-mock-compiler.yml pull``,
and you can ignore them:

```bash
ERROR: for submission-ui  manifest for arxiv/submission-ui:latest not found: manifest unknown: manifest unknown

ERROR: for mock-compiler-api  pull access denied for arxiv/mock-compiler, repository does not exist or may require
'docker login': denied: requested access to the resource is denied

ERROR: for mock-classifier  pull access denied for arxiv/mock-classifier, repository does not exist or may require
'docker login': denied: requested access to the resource is denied
ERROR: pull access denied for arxiv/mock-classifier, repository does not exist or may require
'docker login': denied: requested access to the resource is denied
```

From this point on (after issuing docker-compose up command) the output is similar for both the mock and full
compiler options. You may skip ahead to the section on what to expect during startup.

### Using your own PDF and compilation log.

In the event you do not want to install the compiler yet want to see what a specific compilation
product looks like you may grab the PDF and compilation log from the production arXiv system and
install these files as data for the mock compiler service.

The PDF and log returned by the mock compiler service are stored in the 'mock-services/data/compiler'
directory.

Simply install your new data files, rebuild the mock compiler service, and bring up the submission-ui.

When using the mock-compiler service you will get the same PDF and compilation log for every submission.
The idea behind the mock compiler service is to let you work through the entire submission process workflow
without the hassle of installing the compiler service.

## Quick start using arXiv Compiler service (with actual TeX compilation)

There are now multiple converter images that may be configured to compile TeX source.
Most converter images contain a single TeX tree (to reduce size) along with one
very large converter image that contains the complete set of all arXiv TeX trees (14.5G).
At the current time you may configure a single converter image to compile TeX sources.

The following TeX trees are available: TeX Live 2016 (most recent); TeX Live 2011;
TeX Live 2009; teTeX 2; and teTeX 3. The teTeX 2 tree contains multiple local trees.

Set the CONVERTER_DOCKER_IMAGE environment variable to indicate the converter image
you would like to select.

Please check arXiv's ASW ECR repository for the current list of images.

  All Trees: (14.5G) Contains all trees, submissions uses latest tree.
    626657773168.dkr.ecr.us-east-1.amazonaws.com/arxiv/converter

  TL2016: (7.9G) 2017-02-09
    626657773168.dkr.ecr.us-east-1.amazonaws.com/arxiv/converter-2016

  TL2011: (5.8G) 2011-12-06
    626657773168.dkr.ecr.us-east-1.amazonaws.com/arxiv/converter-2011

  TL2009: (4.9G) 2009-12-31
    626657773168.dkr.ecr.us-east-1.amazonaws.com/arxiv/converter-2009

  teTeX 3: (3.1G) 2006-11-02
    626657773168.dkr.ecr.us-east-1.amazonaws.com/arxiv/converter-tetex-3

  teTeX 2: (3.2G) Uses different binaries and texmf (local tree) versions: 2002-09-01, 2003-01-01, 2004-01-01
    626657773168.dkr.ecr.us-east-1.amazonaws.com/arxiv/converter-tetex-2

There are two ways to download and install the converter image: manual and automatic.

The 'automated' method lets the compiler service download the converter image for you. If you set the environment
variable 'CONVERTER_IMAGE_PULL' to 1 in the docker-compose.yml file under both the compiler-api: and
the compiler-worker: sections, and then rebuild/up the compiler service, the compiler service will attempt to download
the image from AWS in the event it does not find it locally. There will be a delay during startup while the converter image
is being downloaded.

The second method is to manually download the converter image(s) you need prior to starting up the
submission UI. This will save time during startup.

The 'CONVERTER_IMAGE_PULL' environment variables are now set to 1 (enabled) by default. You may still want to
manually download the image to speed up startup. In the event you accidently remove the converter image the
compiler service will simply download a fresh copy. This seems like a useful safety feature.

In both cases you will need to configure your AWS credentials prior to attempting converter image download.

In order to let the compiler service download a converter image simply set (including version number**):
```bash
export CONVERTER_DOCKER_IMAGE=626657773168.dkr.ecr.us-east-1.amazonaws.com/arxiv/converter-2009:0.1.0
```
To download manually execute the pull command with the appropriate converter image specification:
```bash
$ docker pull 626657773168.dkr.ecr.us-east-1.amazonaws.com/arxiv/converter:latest
```

** Compiler service seems to get confused when version number is not included. This will be fixed
in a subsequent ticket whe time permits.

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

7. Install awscli, on linux you can do "pip install awscli" or "pipenv install awscli" or look up how to do this on your OS. [Instructions for CLI install from AWS](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-install.html)

8. On the command line run `aws configure` and enter the AWS access key ID, AWS secret access key and us-east-1 for region when prompted. Format can be 'json' 'text' or 'table' and is your preference.

To test if you have access to ECR run:
`aws ecr list-images --repository-name arxiv/converter`
You should get a response of no error and a list of docker images.

### Quick start commands (full compiler)

Make sure you have your AWS settings configured properly before proceeding ([see above](#aws-credentials)).

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

## What to expect during startup (hint: lots of logs messages from the various microservices)

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

Add the '-f' flag when using the mock compiler service:

```bash
docker-compose -f docker-compose-mock-compiler.yml rm -v
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
