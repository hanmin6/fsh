"""Opt-in tests: fictional data on the isolated loopback CRM only."""
import json
import os
import subprocess
import unittest
import uuid
from tests import test_alibaba_sync_runtime as sync_runtime
from tests.test_alibaba_sync_runtime import admin_api, api, sp, BASE, assert_loopback_base_url


class BossInsightsRuntime(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.getenv('RUN_BOSS_INSIGHTS_RUNTIME') != '1': raise unittest.SkipTest('opt-in isolated CRM tests')
        assert_loopback_base_url()
        if ':18082/' not in BASE: raise RuntimeError('Dedicated boss test stack must use port 18082')
        cls.tag = uuid.uuid4().hex[:12]
        registration, cls.headers = sync_runtime.AlibabaSyncRuntime.register_agent('history-test-' + cls.tag)
        cls.ids = []
        for n in range(2):
            _, result = api('/Fusanhe/alibaba/sync', 'POST', {
                'requestId': 'history-' + cls.tag + str(n), 'jobId': 'job-' + cls.tag,
                'accountHandle': 'history-fixture-' + cls.tag, 'syncMode': 'backfill', 'finalBatch': True,
                'conversation': {'inquiryId': 'HISTORY-' + cls.tag + str(n), 'buyerName': 'Fictional History Buyer', 'buyerExternalId': 'fixture-' + cls.tag + str(n)},
                'messages': [{'externalId': 'm-' + cls.tag + str(n), 'body': 'Please send a sample.', 'direction': 'inbound', 'sentAt': '2026-09-20T10:00:00Z', 'sourceSequence': 1, 'timestampConfidence': 'high', 'messageType': 'chat'}]
            }, headers=cls.headers)
            cls.ids.append(result['conversationId'])
        _, role = admin_api('/Role', 'POST', {'name':'History read-only '+cls.tag, 'data':{
            'ExternalConversation':{'read':'own','edit':'no','create':'no','delete':'no'},
            'ExternalMessage':{'read':'all','edit':'no','create':'no','delete':'no'},
        }})
        cls.login = 'history-' + cls.tag
        cls.password = 'Fixture-History-Read-Only-2026'
        _, user = admin_api('/User','POST',{'userName':cls.login,'lastName':'History fixture','type':'regular','password':cls.password,'passwordConfirm':cls.password,'rolesIds':[role['id']]})
        admin_api('/ExternalConversation/'+cls.ids[0],'PATCH',{'assignedUserId':user['id']})

    def test_paging_search_and_unknown_coverage(self):
        _, data = admin_api('/Fusanhe/insights?q='+self.tag+'&limit=1')
        self.assertEqual(data['total'],2); self.assertEqual(len(data['list']),1)
        _, page = admin_api('/Fusanhe/insights?q='+self.tag+'&limit=1&offset=1')
        self.assertNotEqual(data['list'][0]['id'],page['list'][0]['id'])
        self.assertIsNone(data['coverage']['platformVisible']); self.assertFalse(data['coverage']['reconciled'])
        self.assertTrue(data['outboundPaused'])

    def test_readonly_user_sees_only_own_and_cannot_mutate(self):
        auth=(self.login,self.password)
        _, data=api('/Fusanhe/insights?q='+self.tag,auth=auth)
        self.assertEqual(data['scope'],'own'); self.assertEqual(data['total'],1)
        self.assertEqual(data['coverage']['imported'],1)
        status,_=api('/Fusanhe/insights/'+self.ids[1],auth=auth,expect_error=True)
        self.assertEqual(status,404)
        status,_=api('/ExternalConversation/'+self.ids[0],'PATCH',{'insightsStatus':'completed'},auth=auth,expect_error=True)
        self.assertEqual(status,403)

    def test_analysis_fields_service_only_and_evidence_acl(self):
        status,data=admin_api('/ExternalConversation/'+self.ids[0],'PATCH',{'insightsStatus':'completed','insightsData':{'summaryZh':'fake'}},expect_error=True)
        self.assertIn(status,[200,403])  # Espo may strip read-only attributes before hooks.
        _, detail=admin_api('/Fusanhe/insights/'+self.ids[0])
        self.assertEqual(detail['analysisStatus'],'pending'); self.assertIsNone(detail['analysis'])

    def test_dashboard_own_counts_do_not_leak(self):
        _, data=api('/Fusanhe/dashboard',auth=(self.login,self.password))
        self.assertEqual(data['todayInquiries'],1)
        self.assertLessEqual(sum(data['byAssignedUser'].values()),1)
        self.assertEqual(data['aiDrafts'],0)

    def test_anonymous_denied(self):
        status,_=api('/Fusanhe/insights',expect_error=True)
        self.assertEqual(status,401)

    def test_source_snapshot_and_new_message_invalidates(self):
        cid=self.ids[0]
        source="""<?php
register_shutdown_function(function () { $e=error_get_last(); if ($e && $e['type']===E_ERROR) echo json_encode($e); });
require 'bootstrap.php';
$app=new Espo\\Core\\Application();
$container=$app->getContainer();
$container->get('injectableFactory')->create(\\Espo\\Core\\ApplicationUser::class)->setupSystemUser();
$em=$container->get('entityManager');
$c=$em->getEntityById('ExternalConversation', %s);
$worker=new Espo\\Custom\\Tools\\Fusanhe\\HistoryAnalysisWorker($em,new Espo\\Custom\\Tools\\Fusanhe\\ServiceKernel($em),new Espo\\Custom\\Tools\\Fusanhe\\HistoryAiProvider());
$s=$worker->snapshot($c);
$c->set(['insightsVersion'=>$s['version'],'insightsStatus'=>'completed']);
$em->saveEntity($c,['fusanheInsights'=>true]);
echo json_encode(['version'=>$s['version'],'input'=>$s['input']]);
""" % json.dumps(cid)
        cmd=['docker','compose','-p','fusanhe-phase1-test','--env-file','.env.test','-f','tests/phase1-compose.yaml','exec','-T','espocrm','php']
        result=subprocess.run(cmd,input=source,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr + result.stdout)
        snapshot=json.loads(result.stdout)
        self.assertNotIn('Please',json.dumps(snapshot['input']))
        self.assertEqual(snapshot['input']['messageCounts']['inbound'],1)
        _, conversation=admin_api('/ExternalConversation/'+cid)
        _, channel=admin_api('/ExternalChannel/'+conversation['channelId'])
        api('/Fusanhe/alibaba/sync','POST',{
            'requestId':'new-'+self.tag,'jobId':'job-new-'+self.tag,'accountHandle':channel['accountHandle'],'syncMode':'incremental','finalBatch':True,
            'conversation':{'inquiryId':conversation['externalId'],'buyerExternalId':conversation['externalUserId'],'buyerName':'Fictional History Buyer'},
            'messages':[{'externalId':'new-'+self.tag,'body':'New sample question','direction':'inbound','sentAt':'2026-09-23T10:00:00Z','sourceSequence':2,'timestampConfidence':'high','messageType':'chat'}]
        },headers=self.headers)
        _, detail=admin_api('/Fusanhe/insights/'+cid)
        self.assertEqual(detail['analysisStatus'],'stale')
