"""Read-only live checks; run with FUSANHE_TEST_PUBLIC_WORKSPACE=1 after enabling."""
import base64
import http.cookiejar
import json
import os
import unittest
import urllib.error
import urllib.request


@unittest.skipUnless(os.getenv('FUSANHE_TEST_PUBLIC_WORKSPACE') == '1', 'public workspace not explicitly selected')
class PublicWorkspace(unittest.TestCase):
    def setUp(self):
        self.base = os.getenv('ESPOCRM_API_URL', 'http://localhost:8080/api/v1').rstrip('/')
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def request(self, path, credential, by_token=False):
        encoded = base64.b64encode(credential.encode()).decode()
        headers = {'Authorization': 'Basic ' + encoded, 'Espo-Authorization': encoded,
                   'Espo-Authorization-By-Token': str(by_token).lower(),
                   'Espo-Authorization-Create-Token-Secret': 'true'}
        try:
            with self.opener.open(urllib.request.Request(self.base + '/' + path, headers=headers), timeout=15) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, {}

    def session(self):
        status, data = self.request('App/user', '**workspace:public-workspace')
        self.assertEqual(status, 200)
        self.assertEqual(data['user']['type'], 'regular')
        self.assertEqual(data['user']['userName'], 'fusanhe-workspace')
        return data['user']['userName'] + ':' + data['token'], data

    def test_editable_business_without_admin_or_execution_rights(self):
        credential, data = self.session()
        table = data['acl']['table']
        for entity in ['Account', 'Lead', 'Task']:
            self.assertEqual(table[entity]['read'], 'all')
            self.assertEqual(table[entity]['edit'], 'all')
            self.assertEqual(table[entity]['create'], 'yes')
            self.assertEqual(table[entity]['delete'], 'no')
            self.assertEqual(self.request(entity + '?maxSize=1', credential, True)[0], 200)
        self.assertEqual(table['OutboundTask']['create'], 'no')
        for path in ['Role?maxSize=1', 'Admin']:
            self.assertEqual(self.request(path, credential, True)[0], 403)

    def test_marker_cannot_select_admin_and_invalid_sessions_fail(self):
        for credential in ['**workspace:wrong', 'admin:public-workspace']:
            self.assertEqual(self.request('App/user', credential)[0], 401)
        self.assertEqual(self.request('App/user', 'fusanhe-workspace:invalid-token', True)[0], 401)

    def test_new_sessions_and_session_resume(self):
        credential, _ = self.session()
        self.assertEqual(self.request('App/user', credential, True)[0], 200)
        self.assertEqual(self.request('App/user', '**workspace:public-workspace')[0], 200)
