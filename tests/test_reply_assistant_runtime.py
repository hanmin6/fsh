"""Opt-in HTTP acceptance against the disposable, loopback-only CRM test stack."""
import base64
import json
import os
import pathlib
import unittest
import urllib.request
import urllib.error
import urllib.parse
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE = os.getenv('REPLY_TEST_API_URL', 'http://127.0.0.1:18088/api/v1')

@unittest.skipUnless(os.getenv('RUN_REPLY_RUNTIME') == '1', 'requires isolated CRM test stack')
class ReplyAssistantRuntime(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if urllib.parse.urlparse(BASE).hostname not in ('localhost','127.0.0.1','::1'):
            raise RuntimeError('Tests require loopback CRM URL')
        # Only committed synthetic test credentials; never read production .env.
        env = dict(line.split('=',1) for line in (ROOT/'.env.test.example').read_text().splitlines() if '=' in line and not line.startswith('#'))
        cls.admin = (env['ESPOCRM_ADMIN_USERNAME'],os.getenv('REPLY_TEST_ADMIN_PASSWORD',env['ESPOCRM_ADMIN_PASSWORD']))
        cls.denied = ('reply-denied-'+uuid.uuid4().hex[:8], 'Synthetic-pass-1234!')
        status,role=cls.call('/Role',{'name':'Reply assistant denied test','data':{'AIReplyDraft':False},'fieldData':{}})
        if status != 200: raise AssertionError('Could not create isolated test role')
        status,_=cls.call('/User',{'userName':cls.denied[0],'password':cls.denied[1],'lastName':'Synthetic User','isActive':True,'rolesIds':[role['id']]})
        if status != 200: raise AssertionError('Could not create isolated test user')

    @classmethod
    def call(cls,path,body,auth='admin'):
        headers={'Content-Type':'application/json'}
        credentials=cls.admin if auth=='admin' else cls.denied if auth=='denied' else None
        if credentials: headers['Authorization']='Basic '+base64.b64encode((':'.join(credentials)).encode()).decode()
        request=urllib.request.Request(BASE+path,json.dumps(body).encode(),headers,method='POST')
        try:
            with urllib.request.urlopen(request,timeout=30) as response:
                return response.status,json.loads(response.read() or '{}')
        except urllib.error.HTTPError as error:
            raw=error.read()
            try: data=json.loads(raw or '{}')
            except json.JSONDecodeError: data={}
            return error.code,data

    def test_unauthenticated_request_is_rejected(self):
        status,_=self.call('/Fusanhe/reply-assistant',{'operation':'analyze','text':'Synthetic inquiry'},auth=None)
        self.assertIn(status,(401,403))

    def test_permission_is_checked_before_ai_call(self):
        status,_=self.call('/Fusanhe/reply-assistant',{'operation':'analyze','text':'Synthetic inquiry'},auth='denied')
        self.assertEqual(status,403)

    def test_invalid_images_and_empty_intent_are_rejected(self):
        for data in ({'operation':'analyze','images':['https://example.invalid/image.png']},{'operation':'generate','text':'hi'}):
            status,body=self.call('/Fusanhe/reply-assistant',data)
            self.assertEqual(status,400)
            self.assertEqual(body['error']['code'],'invalid_request')

    def test_missing_provider_does_not_return_mock(self):
        status,body=self.call('/Fusanhe/reply-assistant',{'operation':'analyze','text':'Synthetic inquiry'})
        self.assertEqual(status,503)
        self.assertEqual(body['error']['code'],'internal_error')
        self.assertNotIn('ok',body)
        self.assertNotIn('result',body)
        self.assertTrue(body['error'].get('requestId'))

if __name__=='__main__': unittest.main()
