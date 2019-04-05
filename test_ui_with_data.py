"""
Test the submission UI with real data!

Based on work from ARXIVNG-457.

Data generated with:

.. code-block:: sql

SELECT sub.*, cat.category, cat.is_primary
FROM arXiv.arXiv_submissions sub, arXiv.arXiv_submission_category cat
WHERE sub.submission_id = cat.submission_id
AND sub.submission_id > 2622999
AND sub.submission_id < 2623999
ORDER BY sub.submission_id DESC;

.. code-block:: bash

   mysql -u root -B arXiv < export_submissions.sql > submissions.tsv

"""

from csv import DictReader
import os
import time
import re
from itertools import groupby
from collections import defaultdict, OrderedDict
from multiprocessing import Pool
from functools import partial

import click
import requests
from bs4 import BeautifulSoup

from arxiv.users.helpers import generate_token
from arxiv.submission.services import classic
from arxiv.users.auth import scopes
from arxiv.users.domain import Category
from http import HTTPStatus as status

from submit.domain import workflow


class GetStageFailed(RuntimeError):
    """Failed to get a stage."""


class PostStageFailed(RuntimeError):
    """Failed when posting data to a stage."""


os.environ['JWT_SECRET'] = 'foosecret'

CSRF_PATTERN = (r'\<input id="csrf_token" name="csrf_token" type="hidden"'
                r' value="([^\"]+)">')


@click.command()
@click.option('--data', help='Path to submission data')
@click.option('--out', help='Path to write output')
@click.option('--endpoint', help='UI endpoint to hit')
def run_test(data, out, endpoint):
    headers = {'Authorization': _new_auth_token()}
    # results = defaultdict(dict)
    with Pool(10) as pool:
        run_test_case_part = partial(run_test_case, endpoint, headers=headers)
        jobs = pool.imap_unordered(run_test_case_part, load_data(data))

        def done(obj):
            if obj is None:
                return
            submission_id, result = obj
            print(submission_id, '::', result)
        [done(obj) for obj in jobs]


def run_test_case(endpoint, datum, headers={}):
    if datum['version'] > 1:    # Skip replacements for now.
        print(f'Replacement: {datum["submission_id"]}')
        return
    if datum['package'] is None or not os.path.exists(datum['package']):
        print(f'No source content for {datum["submission_id"]}')
        return
    if datum['source_format'] not in ['ps', 'tex']:
        print(f'{datum["submission_id"]} is {datum["source_format"]}, skipping for now')
    submission_id = create_submission(endpoint, headers)
    prior_endpoint = None
    result = OrderedDict()
    for stage in workflow.SubmissionWorkflow.ORDER:
        if stage in data_getters:
            try:
                test_runners[stage](endpoint, stage, datum, submission_id, headers)
            except GetStageFailed as e:
                result[prior_endpoint] = 0
                # results[datum['submission_id']]
                print('%s %s (bounced back)' % (str(e), prior_endpoint))
                break
            except PostStageFailed as e:
                result[stage.endpoint] = 0
                # results[datum['submission_id']]
                print('%s %s (on post)' % (str(e), stage.endpoint))
                break
            prior_endpoint = stage.endpoint
            result[stage.endpoint] = 1
            # results[datum['submission_id']][stage.endpoint] = 1
    if all([v == 1 for v in result.values()]):
        print(datum['submission_id'], 'Succeeded!')
    return datum['submission_id'], result


def create_submission(base_url, headers):
    response = requests.get(base_url.rstrip("/"), headers=headers)
    csrf_token = _parse_csrf_token(response.content)
    response = requests.post(base_url.rstrip("/"),
                             data={'csrf_token': csrf_token},
                             headers=headers, allow_redirects=False)
    loc = response.headers['Location']
    return int(loc.split(base_url, 1)[1].split('/')[1])


def test_stage(base_url, stage, datum, submission_id, headers):
    if stage == workflow.FileUpload:
        return test_upload(base_url, stage, datum, submission_id, headers)
    elif stage == workflow.Process:
        return test_compile(base_url, stage, datum, submission_id, headers)
    response = get_form(base_url, stage, headers, submission_id)
    if response.status_code != status.OK:
        raise GetStageFailed('Failed at %s' % stage.endpoint)

    csrf_token = _parse_csrf_token(response.content)
    response = post_form(base_url, stage, datum, csrf_token, headers,
                         submission_id)

    if response.status_code != status.SEE_OTHER:
        print(datum['submission_id'], stage.endpoint,
              parse_errors(response.content.decode('utf-8')))
        raise PostStageFailed('Failed at %s' % stage.endpoint)


def parse_errors(content):
    soup = BeautifulSoup(content, 'html.parser')
    return [elem.get_text() for elem in soup.find_all(class_="field-error")]


def get_form(base_url, stage, headers, submission_id):
    target = f'{base_url.rstrip("/")}/{submission_id}/{stage.endpoint}'
    return requests.get(target, headers=headers, allow_redirects=False)


def post_form(base_url, stage, datum, csrf_token, headers, submission_id):
    request_data, files_data = data_getters[stage](datum)
    request_data.update({'csrf_token': csrf_token, 'action': 'next'})
    target = f'{base_url.rstrip("/")}/{submission_id}/{stage.endpoint}'
    payload = dict(data=request_data, headers=headers)
    return requests.post(target, **payload, allow_redirects=False)


def test_upload(base_url, stage, datum, submission_id, headers):
    # Get the upload form.
    response = get_form(base_url, stage, headers, submission_id)
    if response.status_code != status.OK:
        raise GetStageFailed('Failed at %s' % stage.endpoint)
    csrf_token = _parse_csrf_token(response.content)

    # Upload files.
    request_data, files_data = data_getters[stage](datum)
    request_data.update({'csrf_token': csrf_token})
    target = f'{base_url.rstrip("/")}/{submission_id}/{stage.endpoint}'
    payload = dict(data=request_data, headers=headers)
    if files_data:
        payload.update(dict(files=files_data))
    response = requests.post(target, **payload, allow_redirects=False)
    if response.status_code != status.SEE_OTHER:
        print(datum['submission_id'], stage.endpoint,
              parse_errors(response.content.decode('utf-8')))
        raise PostStageFailed('Failed at %s (upload)' % stage.endpoint)

    # Get the upload form again.
    response = get_form(base_url, stage, headers, submission_id)
    if response.status_code != status.OK:
        raise GetStageFailed('Failed at %s' % stage.endpoint)
    csrf_token = _parse_csrf_token(response.content)

    # Proceed to next stage.
    csrf_token = _parse_csrf_token(response.content)
    request_data = {'csrf_token': csrf_token, 'action': 'next'}
    payload = dict(data=request_data, headers=headers)
    response = requests.post(target, **payload, allow_redirects=False)
    if response.status_code != status.SEE_OTHER:
        print(datum['submission_id'], stage.endpoint,
              parse_errors(response.content.decode('utf-8')))
        raise PostStageFailed('Failed at %s (proceed)' % stage.endpoint)


def test_compile(base_url, stage, datum, submission_id, headers):
    # Get the process form.
    response = get_form(base_url, stage, headers, submission_id)
    if response.status_code != status.OK:
        raise GetStageFailed('Failed at %s' % stage.endpoint)
    csrf_token = _parse_csrf_token(response.content)

    # POST with no action starts compilation.
    request_data, files_data = data_getters[stage](datum)
    request_data.update({'csrf_token': csrf_token})
    target = f'{base_url.rstrip("/")}/{submission_id}/{stage.endpoint}'
    payload = dict(data=request_data, headers=headers)
    response = requests.post(target, **payload, allow_redirects=False)
    if response.status_code != status.SEE_OTHER:
        print(datum['submission_id'], stage.endpoint,
              parse_errors(response.content.decode('utf-8')))
        raise PostStageFailed('Failed at %s (upload)' % stage.endpoint)

    response = get_form(base_url, stage, headers, submission_id)
    if response.status_code != status.OK:
        raise GetStageFailed('Failed at %s' % stage.endpoint)
    csrf_token = _parse_csrf_token(response.content)

    soup = BeautifulSoup(response.content.decode('utf-8'), 'html.parser')
    stat_elem = soup.find(id="status-message")
    if stat_elem:
        datstat = stat_elem["data-status"]
    else:
        datstat = 'failed'
    while datstat == 'in_progress':
        time.sleep(2)
        response = get_form(base_url, stage, headers, submission_id)
        if response.status_code != status.OK:
            raise GetStageFailed('Failed at %s' % stage.endpoint)
        csrf_token = _parse_csrf_token(response.content)
        soup = BeautifulSoup(response.content.decode('utf-8'), 'html.parser')
        stat_elem = soup.find(id="status-message")
        if stat_elem:
            datstat = stat_elem["data-status"]
        else:
            datstat = 'failed'

    if datstat == 'failed':
        raise PostStageFailed('Processing failed')


def load_data(data):
    def _source_path(datum):
        submission_id = str(datum['submission_id'])
        return f"{submission_id[:4]}/{submission_id}/src"

    def rewrite_source_path(datum, path):
        if not path:
            return None
        data_dir, _ = os.path.split(data)
        frag = path.split('/data/new/')[1]
        return os.path.join(data_dir, frag)

    handlers = [
        ('package', rewrite_source_path),
    ]

    def handle_fields(datum):
        for field, handler in handlers:
            datum[field] = handler(datum, datum[field])
        return datum

    with open(data) as f:
        rows = groupby(DictReader(f, delimiter='\t'),
                       key=lambda row: row['submission_id'])
        for submission_id, row_group in rows:
            row_group = [row for row in row_group]
            datum = combine_rows(row_group)

            yield handle_fields(coerce_to_int(replace_null_values(datum)))


def replace_null_values(datum):
    return {k: None if v == 'NULL' else v for k, v in datum.items()}


def coerce_to_int(datum):
    def _try_int(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return value
    return {k: _try_int(v) for k, v in datum.items()}


def combine_rows(datum_group):
    datum = datum_group[0]
    for row in datum_group:
        if row['is_primary'] == 'NULL':
            continue

        if row['is_primary'] == '1':
            datum['primary_category'] = row['category']
            break
        if 'secondary_categories' not in datum:
            datum['secondary_categories'] = []
        datum['secondary_categories'].append(row['category'])
    return datum


def _parse_csrf_token(raw):
    try:
        match = re.search(CSRF_PATTERN, raw.decode('utf-8'))
        token = match.group(1)
    except AttributeError:
        print('Could not find CSRF token')
    return token


def _new_auth_token():
    return generate_token(
        '10', 'foo@bar.com', 'foouser',
        scope=[scopes.READ_PUBLIC,
               scopes.CREATE_SUBMISSION,
               scopes.EDIT_SUBMISSION,
               scopes.VIEW_SUBMISSION,
               scopes.DELETE_SUBMISSION,
               scopes.READ_UPLOAD,
               scopes.WRITE_UPLOAD,
               scopes.DELETE_UPLOAD_FILE,
               scopes.READ_UPLOAD_LOGS,
               scopes.READ_COMPILE,
               scopes.CREATE_COMPILE],
        endorsements=["*.*"])


def get_verify_user_data(datum):
    return {'verify_user': 'y' if datum['userinfo'] == 1 else 'n'}, None


def get_authorship_data(datum):
    return {'authorship': 'y' if datum['is_author'] == 1 else 'n'}, None


def get_license_data(datum):
    return {'license': datum['license']}, None


def get_policy_data(datum):
    return {'policy': 'y' if datum['agree_policy'] == 1 else 'n'}, None


def get_primary_classification_data(datum):
    return {'category': datum.get('primary_category', None)}, None


def get_metadata_data(datum):
    return {
        'title': datum['title'],
        'abstract': datum['abstract'],
        'comments': datum['comments'],
        'authors_display': datum['authors']
    }, None


def get_optional_metadata_data(datum):
    return {
        'acm_class': datum['acm_class'],
        'msc_class': datum['msc_class'],
        'doi': datum['doi'],
        'journal_ref': datum['journal_ref'],
        'report_num': datum['report_num'],
    }, None


def get_final_preview_data(datum):
    return {'proceed': 'y' if datum['viewed'] == 1 else 'n'}, None


def get_file_upload_data(datum):
    if datum['package'] and os.path.exists(datum['package']):
        return {}, {'file': open(datum['package'], 'rb')}
    return {}, {}


def get_process_data(datum):
    return {}, {}


data_getters = {
    workflow.VerifyUser: get_verify_user_data,
    workflow.Authorship: get_authorship_data,
    workflow.License: get_license_data,
    workflow.Policy: get_policy_data,
    workflow.Classification: get_primary_classification_data,
    workflow.CrossList: lambda datum: ({}, {}),
    workflow.FileUpload: get_file_upload_data,
    workflow.Process: get_process_data,
    workflow.Metadata: get_metadata_data,
    workflow.OptionalMetadata: get_optional_metadata_data,
    workflow.FinalPreview: get_final_preview_data
}

test_runners = {
    workflow.VerifyUser: test_stage,
    workflow.Authorship: test_stage,
    workflow.License: test_stage,
    workflow.Policy: test_stage,
    workflow.Classification: test_stage,
    workflow.CrossList: test_stage,
    workflow.FileUpload: test_upload,
    workflow.Process: test_compile,
    workflow.Metadata: test_stage,
    workflow.OptionalMetadata: test_stage,
    workflow.FinalPreview: test_stage
}


if __name__ == '__main__':
    run_test()
