"""Tests for the submission system integration.

This differs from the test_workflow in that this tests the submission
system as an integrated whole from the outside via HTTP requests. This
contacts a submission system at a URL via HTTP. test_workflow.py
creates the flask app and interacts with that.

WARNING: This test is written in a very stateful manner. So the tests must be run
in order.
"""

import logging
import os
import tempfile
import unittest
from pathlib import Path
import pprint
import requests
import time

from requests_toolbelt.multipart.encoder import MultipartEncoder


from submit.factory import create_ui_web_app
from arxiv.users.helpers import generate_token
from arxiv.users.auth import scopes
from arxiv.users.domain import Category
from http import HTTPStatus as status
from submit.tests.csrf_util import parse_csrf_token


# def new_user():
#     app = create_ui_web_app()
#     os.environ['JWT_SECRET'] = 'foosecret'
#     _, dbfile = tempfile.mkstemp(suffix='.db')
#     app.config['CLASSIC_DATABASE_URI'] = f'sqlite:///{dbfile}'
#     token = generate_token('1', 'foo@bar.com', 'foouser',
#                            scope=[scopes.CREATE_SUBMISSION,
#                                   scopes.EDIT_SUBMISSION,
#                                   scopes.VIEW_SUBMISSION,
#                                   scopes.READ_UPLOAD,
#                                   scopes.WRITE_UPLOAD,
#                                   scopes.DELETE_UPLOAD_FILE],
#                            endorsements=[
#                                Category('astro-ph.GA'),
#                                Category('astro-ph.CO'),
#                            ])
#     token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzZXNzaW9uX2lkIjoiODQzYWFjZTYtMGY3My00ODQ1LWJlMDAtNzEwZjZkNjMwYmVjIiwic3RhcnRfdGltZSI6IjIwMjAtMDgtMDNUMTQ6NDE6MTAuMDkwNTk4LTA0OjAwIiwidXNlciI6eyJ1c2VybmFtZSI6ImFydGFiYTE4NjRAeWFob28uY29tIiwiZW1haWwiOiJhcnRhYmExODY0QHlhaG9vLmNvbSIsInVzZXJfaWQiOjEwLCJuYW1lIjp7ImZvcmVuYW1lIjoiXHUwNjQ2XHUwNmNjXHUwNmE5XHUwNmNjIiwic3VybmFtZSI6Ilx1MDY0NVx1MDYyY1x1MDYyYVx1MDY0N1x1MDYyZlx1MDZjYyIsInN1ZmZpeCI6Ilx1MDYyN1x1MDYzM1x1MDYyYVx1MDYyN1x1MDYyZiJ9LCJwcm9maWxlIjp7ImFmZmlsaWF0aW9uIjoiQ29ybmVsbCBVbml2ZXJzaXR5IiwiY291bnRyeSI6InVzIiwicmFuayI6Mywic3VibWlzc2lvbl9ncm91cHMiOlsiZ3JwX3BoeXNpY3MiXSwiZGVmYXVsdF9jYXRlZ29yeSI6ImFzdHJvLXBoLkdBIiwiaG9tZXBhZ2VfdXJsIjoiIiwicmVtZW1iZXJfbWUiOnRydWV9LCJ2ZXJpZmllZCI6ZmFsc2V9LCJjbGllbnQiOm51bGwsImVuZF90aW1lIjoiMjAyMC0wOC0wNFQwMDo0MToxMC4wOTA1OTgtMDQ6MDAiLCJhdXRob3JpemF0aW9ucyI6eyJjbGFzc2ljIjowLCJlbmRvcnNlbWVudHMiOlsiKi4qIl0sInNjb3BlcyI6W3siZG9tYWluIjoicHVibGljIiwiYWN0aW9uIjoicmVhZCIsInJlc291cmNlIjpudWxsfSx7ImRvbWFpbiI6InN1Ym1pc3Npb24iLCJhY3Rpb24iOiJjcmVhdGUiLCJyZXNvdXJjZSI6bnVsbH0seyJkb21haW4iOiJzdWJtaXNzaW9uIiwiYWN0aW9uIjoidXBkYXRlIiwicmVzb3VyY2UiOm51bGx9LHsiZG9tYWluIjoic3VibWlzc2lvbiIsImFjdGlvbiI6InJlYWQiLCJyZXNvdXJjZSI6bnVsbH0seyJkb21haW4iOiJzdWJtaXNzaW9uIiwiYWN0aW9uIjoiZGVsZXRlIiwicmVzb3VyY2UiOm51bGx9LHsiZG9tYWluIjoidXBsb2FkIiwiYWN0aW9uIjoicmVhZCIsInJlc291cmNlIjpudWxsfSx7ImRvbWFpbiI6InVwbG9hZCIsImFjdGlvbiI6InVwZGF0ZSIsInJlc291cmNlIjpudWxsfSx7ImRvbWFpbiI6InVwbG9hZCIsImFjdGlvbiI6ImRlbGV0ZSIsInJlc291cmNlIjpudWxsfSx7ImRvbWFpbiI6InVwbG9hZCIsImFjdGlvbiI6InJlYWRfbG9ncyIsInJlc291cmNlIjpudWxsfSx7ImRvbWFpbiI6ImNvbXBpbGUiLCJhY3Rpb24iOiJyZWFkIiwicmVzb3VyY2UiOm51bGx9LHsiZG9tYWluIjoiY29tcGlsZSIsImFjdGlvbiI6ImNyZWF0ZSIsInJlc291cmNlIjpudWxsfSx7ImRvbWFpbiI6InByZXZpZXciLCJhY3Rpb24iOiJyZWFkIiwicmVzb3VyY2UiOm51bGx9LHsiZG9tYWluIjoicHJldmlldyIsImFjdGlvbiI6ImNyZWF0ZSIsInJlc291cmNlIjpudWxsfV19LCJpcF9hZGRyZXNzIjpudWxsLCJyZW1vdGVfaG9zdCI6bnVsbCwibm9uY2UiOm51bGx9.UsNvIrqCTIAhwd3WU8-zrOAFpgRvi0dgYpY9YMy72EE"
#     return (token, dbfile)


class TestSubmissionIntegration(unittest.TestCase):
    """Tests submission system."""
    @classmethod
    def setUp(self):
        self.token = os.environ.get('INTEGRATION_JWT')
        self.url = os.environ.get('INTEGRATION_URL', 'http://localhost:5000')
        
        self.headers = {'Authorization': self.token}

        logging.basicConfig()
        self.log = logging.getLogger(__name__)
        self.log.setLevel(logging.DEBUG)
        self.next_page = None
        self.process_page_timeout = 120 # sec


    def check_response(self, res):
        self.assertEqual(res.status_code, status.SEE_OTHER, f"Should get SEE_OTHER but was {res.status_code}")
        self.assertIn('Location', res.headers)
        self.next_page = res.headers['Location']

    def unloggedin_page(self):
        res = requests.get(self.url, allow_redirects=False)
        self.assertNotEqual(res.status_code, 200,
                            "page without Authorization must not return a 200")


    def home_page(self):
        res = requests.get(self.url, headers=self.headers,
                           allow_redirects=False)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers['content-type'],
                         'text/html; charset=utf-8')
        self.csrf = parse_csrf_token(res)
        self.assertIn('Welcome', res.text)

    def create_submission(self):
        res = requests.get(self.url, headers=self.headers, allow_redirects=False)
        self.assertEqual(res.status_code, 200)
        self.assertIn('Welcome', res.text)

        res = requests.post(self.url + "/", headers=self.headers,
                            data={'new': 'new', 'csrf_token': parse_csrf_token(res)},
                            allow_redirects=False)
        self.assertTrue(status.SEE_OTHER, f"Should get SEE_OTHER but was {res.status_code}")
        
        self.check_response(res)

    def verify_user_page(self):
        self.assertIn('verify_user', self.next_page,
                      "next page should be to verify_user")

        res = requests.get(self.next_page, headers=self.headers, allow_redirects=False)
        self.assertEqual(res.status_code, 200)
        self.assertIn('By checking this box, I verify that my user information is', res.text)

        # here we're reusing next_page, that's not great maybe find it in the html
        res = requests.post(self.next_page, data={'verify_user': 'true',
                                                  'action': 'next',
                                                  'csrf_token': parse_csrf_token(res)},
                            headers=self.headers,
                            allow_redirects=False)
        self.check_response(res)

    def authorship_page(self):
        self.assertIn('authorship', self.next_page, "next page should be to authorship")
        res = requests.get(self.next_page, headers=self.headers)
        self.assertEqual(res.status_code, 200)
        self.assertIn('I am an author of this paper', res.text)
        res = requests.post(self.next_page,
                            data={'authorship': 'y',
                                  'action': 'next',
                                  'csrf_token': parse_csrf_token(res)},
                            headers=self.headers,
                            allow_redirects=False)
        self.check_response(res)

    def license_page(self):
        self.assertIn('license', self.next_page, "next page should be to license")
        res = requests.get(self.next_page, headers=self.headers)
        self.assertEqual(res.status_code, 200)
        self.assertIn('Select a License', res.text)
        res = requests.post(self.next_page,
                            data={'license': 'http://arxiv.org/licenses/nonexclusive-distrib/1.0/',
                                  'action': 'next',
                                  'csrf_token': parse_csrf_token(res)},
                            headers=self.headers,
                            allow_redirects=False)
        self.check_response(res)

    def policy_page(self):
        self.assertIn('policy', self.next_page, "URL should be to policy")
        res = requests.get(self.next_page, headers=self.headers)
        self.assertEqual(res.status_code, 200)
        self.assertIn('By checking this box, I agree to the policies', res.text)
        res = requests.post(self.next_page,
                            data={'policy': 'y',
                                  'action': 'next',
                                  'csrf_token': parse_csrf_token(res)},
                            headers=self.headers,
                            allow_redirects=False)
        self.check_response(res)

    def primary_page(self):
        self.assertIn('classification', self.next_page, "URL should be to primary classification")
        res = requests.get(self.next_page, headers=self.headers)
        self.assertEqual(res.status_code, 200)
        self.assertIn('Choose a Primary Classification', res.text)
        res = requests.post(self.next_page,
                            data={'category': 'hep-ph',
                                  'action': 'next',
                                  'csrf_token': parse_csrf_token(res)},
                            headers=self.headers,
                            allow_redirects=False)
        self.check_response(res)
        

    def cross_page(self):
        self.assertIn('cross', self.next_page, "URL should be to cross lists")
        res = requests.get(self.next_page, headers=self.headers)
        self.assertEqual(res.status_code, 200)
        self.assertIn('Choose Cross-List Classifications', res.text)
        res = requests.post(self.next_page,
                            data={'category': 'hep-ex',
                                  'csrf_token': parse_csrf_token(res)},
                            headers=self.headers)
        self.assertEqual(res.status_code, 200)
        
        res = requests.post(self.next_page,
                            data={'category': 'astro-ph.CO',
                                  'csrf_token': parse_csrf_token(res)},
                            headers=self.headers)
        self.assertEqual(res.status_code, 200)
        
        # cross page is a little different in that you post the crosses and then
        # do the next.
        res = requests.post(self.next_page,
                            data={'action':'next',
                                  'csrf_token': parse_csrf_token(res)},
                            headers=self.headers, allow_redirects=False)
        self.check_response(res)

        
    def upload_page(self):
        self.log.debug(f'in upload_page_page {self.next_page}')
        self.assertIn('upload', self.next_page, "URL should be to upload files")
        res = requests.get(self.next_page, headers=self.headers, allow_redirects=False)
        self.assertEqual(res.status_code, 200)
        self.assertIn('Upload Files', res.text)

        # Upload a file
        upload_path = Path(os.path.abspath(__file__)).parent / 'upload2.tar.gz'                        
        with open(upload_path, 'rb') as upload_file:
            multipart = MultipartEncoder(fields={
                'file': ('upload2.tar.gz', upload_file, 'application/gzip'),
                'csrf_token' : parse_csrf_token(res),
            })
            fu_headers={'Content-Type': multipart.content_type}
            fu_headers.update( self.headers )

            res = requests.post(self.next_page,
                                data=multipart,
                                headers=fu_headers, allow_redirects=False)

        self.assertEqual(res.status_code, 200)
        self.assertIn('gtart_a.cls', res.text, "gtart_a.cls from upload2.tar.gz should be in page text")

        # go to next stage
        res = requests.post(self.next_page, # should still be file upload page
                            data={'action':'next', 'csrf_token': parse_csrf_token(res)},
                            headers=self.headers, allow_redirects=False)
        self.check_response(res)

    def process_page(self):
        self.log.debug(f'in process_page {self.next_page}')
        self.assertIn('process', self.next_page, "URL should be to process step")
        res = requests.get(self.next_page, headers=self.headers, allow_redirects=False)
        self.assertEqual(res.status_code, 200)
        self.assertIn('Process Files', res.text)

        #request TeX processing
        res = requests.post(self.next_page, data={'csrf_token': parse_csrf_token(res)},
                            headers=self.headers, allow_redirects=False)
        self.assertEqual(res.status_code, 200)

        #wait for TeX processing
        success, timeout, start = False, False, time.time()
        while not success and not time.time() > start + self.process_page_timeout:
            self.log.debug(f'Requesting {self.next_page}')
            res = requests.get(self.next_page,
                               headers=self.headers, allow_redirects=False)
            success = 'TeXLive Compiler Summary' in res.text
            if success:
                break
            time.sleep(1)

        self.assertTrue(success,
                        'Failed to process and get tex compiler summary after {self.process_page_timeout} sec.')

        #goto next page
        res = requests.post(self.next_page, # should still be process page
                            data={'action':'next', 'csrf_token': parse_csrf_token(res)},
                            headers=self.headers, allow_redirects=False)
        self.check_response(res)
        
    def metadata_page(self):
        pass

    def optional_metadata_page(self):
        pass

    def final_preview_page(self):
        pass

    def test_submission_system_basic(self):
        """Create, upload files, process TeX and submit a submission."""
        page_test_names = [
            "unloggedin_page",
            "home_page",
            "create_submission",
            "verify_user_page",
            "authorship_page",
            "license_page",
            "policy_page",
            "primary_page",
            "cross_page",
            "upload_page",
            "process_page",
            "metadata_page",
            "optional_metadata_page",
            "final_preview_page",
        ]
        test_methods = [getattr(self, methname)
                        for methname in page_test_names]
        for page_test in test_methods:
            page_test()


if __name__ == '__main__':
    unittest.main()
