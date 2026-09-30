"""Fictional, opt-in checks of rating persistence and multi-platform insights."""
import os
import unittest
import uuid
from tests.test_alibaba_sync_runtime import admin_api, assert_loopback_base_url, BASE

class UnifiedCrmRuntime(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.getenv('RUN_UNIFIED_CRM_RUNTIME') != '1':
            raise unittest.SkipTest('requires isolated UI test CRM')
        assert_loopback_base_url()
        if ':18082/' not in BASE:
            raise RuntimeError('Use the dedicated isolated test CRM on port 18082')

    def test_rating_rationale_and_server_owned_confirmation(self):
        _, account = admin_api('/Account','POST',{'name':'Fictional UI Rating '+uuid.uuid4().hex[:8]})
        path='/Account/'+account['id']
        status,_=admin_api(path,'PATCH',{'rating':'S','ratingReason':''},expect_error=True)
        self.assertEqual(status,400)
        _, saved=admin_api(path,'PATCH',{'rating':'A','ratingReason':'Fictional demand reviewed','ratingConfirmedAt':'2000-01-01 00:00:00'})
        _, saved=admin_api(path)
        self.assertEqual(saved['rating'],'A')
        self.assertEqual(saved['ratingReason'],'Fictional demand reviewed')
        self.assertTrue(saved['ratingConfirmedById'])
        self.assertNotEqual(saved['ratingConfirmedAt'],'2000-01-01 00:00:00')
        stamp=saved['ratingConfirmedAt']
        _, _=admin_api(path,'PATCH',{'description':'unrelated edit','ratingConfirmedAt':'2000-01-01 00:00:00','ratingConfirmedById':'forged'})
        _, final=admin_api(path)
        self.assertEqual(final['ratingConfirmedAt'],stamp)
        self.assertEqual(final['ratingConfirmedById'],saved['ratingConfirmedById'])

    def test_platform_filter_does_not_mix_conversations(self):
        tag=uuid.uuid4().hex[:10]
        channels={}
        for kind in ['Alibaba','MadeInChina']:
            _, ch=admin_api('/ExternalChannel','POST',{'name':'Fictional UI '+tag+kind,'type':kind,'accountHandle':tag+kind})
            channels[kind]=ch['id']
            admin_api('/ExternalConversation','POST',{'name':'Fictional filter '+tag+kind,'channelId':ch['id'],'externalId':tag+kind,'lastSourceSyncAt':'2026-09-30 01:00:00'})
        # lastSourceSyncAt is integration-owned; seed it through ORM on this isolated stack.
        import subprocess,json
        source="<?php require 'bootstrap.php'; $app=new \\Espo\\Core\\Application(); $em=$app->getContainer()->get('entityManager');"
        for kind,cid in channels.items():
            source+="$r=$em->getRDBRepository('ExternalConversation')->where(['channelId'=>"+json.dumps(cid)+"])->findOne(); $r->set('lastSourceSyncAt','2026-09-30 01:00:00'); $em->saveEntity($r,['skipHooks'=>true]);"
        result=subprocess.run(['docker','compose','-p',os.getenv('COMPOSE_PROJECT_NAME','fusanhe-ui-v1-test'),'--env-file','.env.test','-f',os.getenv('COMPOSE_FILE','tests/unified-ui-compose.yaml'),'exec','-T','espocrm','php'],input=source,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr+result.stdout)
        for kind in channels:
            _, overview=admin_api('/Fusanhe/insights?q='+tag+'&channelType='+kind)
            self.assertEqual(overview['total'],1)
            self.assertIn(kind,overview['list'][0]['name'])
        _, both=admin_api('/Fusanhe/insights?q='+tag)
        self.assertEqual(both['total'],2)
