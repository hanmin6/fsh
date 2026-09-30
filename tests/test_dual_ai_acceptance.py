"""Independent acceptance. Fictional data, loopback isolated CRM, fake transports only.

RUN_DUAL_AI_ACCEPTANCE=1 ESPOCRM_API_URL=http://localhost:18082/api/v1
python3 -m unittest tests.test_dual_ai_acceptance -v
"""
import base64
import json
import os
import subprocess
import unittest
import uuid
from tests.test_alibaba_sync_runtime import admin_api, api, BASE, assert_loopback_base_url

ROOT = os.path.dirname(os.path.dirname(__file__))
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')


def php(source):
    command = ['docker', 'compose', '-p', 'fusanhe-ui-v1-test', '--env-file', '.env.test',
               '-f', 'tests/unified-ui-compose.yaml', 'exec', '-T', 'espocrm', 'php']
    result = subprocess.run(command, input=source, text=True, capture_output=True, cwd=ROOT)
    if result.returncode:
        raise AssertionError(result.stderr + result.stdout)
    return json.loads(result.stdout)


class DualAiAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.getenv('RUN_DUAL_AI_ACCEPTANCE') != '1':
            raise unittest.SkipTest('opt-in isolated acceptance')
        assert_loopback_base_url()
        if ':18082/' not in BASE:
            raise RuntimeError('Use dedicated acceptance CRM port 18082')
        cls.tag = uuid.uuid4().hex[:12]
        _, me = admin_api('/App/user')
        cls.admin_id = me['user']['id']
        _, role = admin_api('/Role', 'POST', {'name': 'Acceptance all ' + cls.tag, 'data': {
            **{s: {'read': 'all', 'create': 'yes', 'edit': 'all', 'delete': 'all'}
               for s in ['CreativePlan', 'MediaJob', 'MediaAsset']},
            'Account': {'read': 'own', 'create': 'yes', 'edit': 'own', 'delete': 'no'},
            'FusanheProduct': {'read': 'no', 'create': 'no', 'edit': 'no', 'delete': 'no'},
        }})
        cls.login = 'accept-' + cls.tag
        cls.password = 'Acceptance-Fictional-Only-2026!'
        _, user = admin_api('/User', 'POST', {'userName': cls.login, 'lastName': 'Acceptance Fictional',
            'type': 'regular', 'password': cls.password, 'passwordConfirm': cls.password,
            'rolesIds': [role['id']]})
        cls.user_id = user['id']
        cls.auth = (cls.login, cls.password)
        cls.data_url = 'data:image/png;base64,' + base64.b64encode(PNG + cls.tag.encode()).decode()
        _, cls.source = admin_api('/Fusanhe/creative/source', 'POST', {'dataUrl': cls.data_url})
        cls.seed = php('''<?php
require 'bootstrap.php'; $app=new Espo\\Core\\Application(); $c=$app->getContainer();
$c->get('injectableFactory')->create(Espo\\Core\\ApplicationUser::class)->setupSystemUser();
$em=$c->get('entityManager'); $k=new Espo\\Custom\\Tools\\Fusanhe\\ServiceKernel($em);
$owner=%s; $source=%s;
$p=$k->create('CreativePlan',['name'=>'Fictional acceptance private plan','assignedUserId'=>$owner,'sourceId'=>$source,'status'=>'completed','idea'=>'Fictional private brief','plans'=>[['name'=>'One','description'=>'Synthetic','motion'=>'Static','use'=>'Review']]]);
$j=$k->create('MediaJob',['name'=>'Fictional acceptance task','assignedUserId'=>$owner,'sourceId'=>$source,'planId'=>$p->getId(),'kind'=>'video','status'=>'failed','providerJobId'=>'fixture-private-task']);
echo json_encode(['CreativePlan'=>$p->getId(),'MediaJob'=>$j->getId(),'MediaAsset'=>$source]);
''' % (json.dumps(cls.admin_id), json.dumps(cls.source['id'])))

    def test_generic_record_apis_cannot_expose_or_mutate_creative_records(self):
        for scope, entity_id in self.seed.items():
            for auth in [self.auth, None]:
                call = (lambda path, method='GET', body=None: admin_api(path, method, body, expect_error=True)) if auth is None else (
                    lambda path, method='GET', body=None: api(path, method, body, auth=auth, expect_error=True))
                for suffix in ['', '/' + entity_id]:
                    code, data = call('/' + scope + suffix)
                    self.assertIn(code, [403, 404], (scope, code, data))
                for method, suffix, body in [('POST', '', {'name': 'forged'}),
                    ('PATCH', '/' + entity_id, {'name': 'forged'}), ('DELETE', '/' + entity_id, None)]:
                    self.assertIn(call('/' + scope + suffix, method, body)[0], [403, 404])

    def test_dedicated_apis_enforce_owner_and_authentication(self):
        for path in ['/Fusanhe/creative/asset/' + self.source['id'] + '/content',
                     '/Fusanhe/media/job/' + self.seed['MediaJob']]:
            self.assertEqual(api(path, auth=self.auth, expect_error=True)[0], 404)
            self.assertEqual(api(path, expect_error=True)[0], 401)
        self.assertEqual(api('/Fusanhe/media/job/' + self.seed['MediaJob'] + '/reconcile',
            'POST', {}, auth=self.auth, expect_error=True)[0], 404)
        _, jobs = api('/Fusanhe/media/jobs', auth=self.auth)
        self.assertNotIn(self.seed['MediaJob'], json.dumps(jobs))

    def test_source_upload_association_acl_and_private_content(self):
        _, account = admin_api('/Account', 'POST', {'name': 'Fictional inaccessible ' + self.tag,
                                                   'assignedUserId': self.admin_id})
        self.assertEqual(api('/Fusanhe/creative/source', 'POST', {'dataUrl': self.data_url,
            'accountId': account['id']}, auth=self.auth, expect_error=True)[0], 403)
        _, own = api('/Fusanhe/creative/source', 'POST', {'dataUrl': self.data_url}, auth=self.auth)
        _, duplicate = api('/Fusanhe/creative/source', 'POST', {'dataUrl': self.data_url}, auth=self.auth)
        self.assertEqual(own['id'], duplicate['id'])
        self.assertNotEqual(own['id'], self.source['id'])
        _, content = api('/Fusanhe/creative/asset/' + own['id'] + '/content', auth=self.auth)
        self.assertEqual(content['dataUrl'], self.data_url)
        self.assertNotIn('fileKey', own)
        self.assertNotIn('sha256', own)

    def test_status_is_honest_and_static_image_generation_disabled(self):
        _, status = admin_api('/Fusanhe/creative/status')
        self.assertFalse(status['media']['capabilities']['image'])
        self.assertFalse(status['planningUsesImage'])
        self.assertIsNone(status['cost'])
        self.assertFalse(status['media']['healthChecked'])
        self.assertFalse(status['text']['healthChecked'])
        self.assertNotIn('API_KEY', json.dumps(status))
        self.assertEqual(api('/Fusanhe/creative/status', expect_error=True)[0], 401)

    def test_scheduled_job_is_registered_and_active(self):
        _, jobs = admin_api('/ScheduledJob?maxSize=100')
        matching = [j for j in jobs['list'] if j['job'] == 'FusanheMediaReconcile']
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]['status'], 'Active')
        self.assertEqual(matching[0]['scheduling'], '* * * * *')

    def test_fake_paid_submission_crash_recovery_archive_and_budgets(self):
        result = php('''<?php
require 'bootstrap.php'; $app=new Espo\\Core\\Application(); $c=$app->getContainer();
$c->get('injectableFactory')->create(Espo\\Core\\ApplicationUser::class)->setupSystemUser();
$em=$c->get('entityManager'); $k=new Espo\\Custom\\Tools\\Fusanhe\\ServiceKernel($em);
$u=$em->getEntityById('User',%s); $other=$em->getEntityById('User',%s);
function accept($ok,$label) {if(!$ok) throw new RuntimeException('Acceptance: '.$label);}
function reject($fn,$label) {try {$fn();} catch(Throwable $e) {return;} throw new RuntimeException('Expected rejection: '.$label);}
foreach(['FUSANHE_TEXT_ENABLED=true','FUSANHE_TEXT_API_BASE_URL=https://fixture.invalid/v1','FUSANHE_TEXT_API_KEY=fictional-text-only','FUSANHE_TEXT_MODEL_GROK=grok-4.7','FUSANHE_TEXT_DEFAULT_MODEL=grok','FUSANHE_MEDIA_ENABLED=true','FUSANHE_MEDIA_API_BASE_URL=https://tokendance.space/gateway/v1','FUSANHE_MEDIA_API_KEY=fictional-media-only','FUSANHE_MEDIA_VIDEO_MODEL=minimax-h3-max','FUSANHE_MEDIA_IMAGE_MODEL=seedream-5.0-lite','FUSANHE_MEDIA_MAX_DAILY_JOBS=100','FUSANHE_MEDIA_MAX_ACTIVE_JOBS=100','FUSANHE_CREATIVE_MAX_DAILY_PLANS=100'] as $env) putenv($env);
$textCalls=0;
$text=new Espo\\Custom\\Tools\\Fusanhe\\TextGateway(function($url,$payload,$key) use (&$textCalls) {
 $textCalls++; accept($key==='fictional-text-only','text key isolation');
 accept(!str_contains(json_encode($payload),'data:image'),'no image prompt');
 $plans=[]; foreach(['One','Two','Three'] as $name) $plans[]=['name'=>$name,'description'=>'Synthetic product scene','motion'=>'Slow pan','use'=>'Review'];
 return [200,json_encode(['model'=>'grok-4.7','choices'=>[['message'=>['content'=>json_encode(['plans'=>$plans])]]],'usage'=>['total_tokens'=>42]])];
});
$tag=bin2hex(random_bytes(8));
$network=new class extends Espo\\Custom\\Tools\\Fusanhe\\MediaNetwork {
 public string $tag;
 public int $posts=0; public int $queries=0; public int $downloads=0; public bool $ambiguous=false; public array $payloads=[];
 public function publicUrl(string $url):array {if($url!=='https://fixture.example/image.png')throw new RuntimeException('blocked');return ['host'=>'fixture.example','address'=>'93.184.216.34'];}
 public function json(string $method,string $url,string $key,?array $body=null):array {
  accept($key==='fictional-media-only','media key isolation');
  if($method==='POST') {$this->posts++;$this->payloads[]=$body;if($this->ambiguous)throw new RuntimeException('fictional timeout');return ['task_id'=>'fixture-task-'.$this->tag.'-'.$this->posts];}
  $this->queries++;return str_contains($url,$this->tag)?['task'=>['status'=>'succeeded','content'=>['url'=>'https://fixture.example/result.mp4']]]:['task'=>['status'=>'queued']];
 }
 public function download(string $url,string $expectedMime):array {$this->downloads++;return ['bytes'=>pack('N',24).'ftypisom'.str_repeat('0',16),'mime'=>'video/mp4'];}
};
$network->tag=$tag;
$media=new Espo\\Custom\\Tools\\Fusanhe\\MediaGateway($network);
$service=new Espo\\Custom\\Tools\\Fusanhe\\CreativeService($em,$k,$text,$media,new Espo\\Custom\\Tools\\Fusanhe\\MediaStorage());
$source=$service->source((object)['dataUrl'=>%s],$u);
$request=(object)['sourceId'=>$source['id'],'idea'=>'Fictional acceptance product','modelChoice'=>'grok','idempotencyKey'=>'accept-plan-'.$tag];
$plan=$service->plan($request,$u);$same=$service->plan($request,$u);
accept($plan['id']===$same['id']&&$textCalls===1,'planning idempotency');
$submit=(object)['planId'=>$plan['id'],'choice'=>0,'kind'=>'video','textOnly'=>true,'idempotencyKey'=>'accept-video-'.$tag];
$job=$service->submit($submit,$u);$same=$service->submit($submit,$u);
accept($job['id']===$same['id']&&$network->posts===1,'paid submission idempotency');
$changed=clone $submit;$changed->choice=1;reject(fn()=>$service->submit($changed,$u),'different payload same key');
$withoutConsent=clone $submit;$withoutConsent->idempotencyKey='accept-consent-'.$tag;$withoutConsent->sourceUrl='https://fixture.example/image.png';
reject(fn()=>$service->submit($withoutConsent,$u),'public source consent');
$image=clone $submit;$image->kind='image';$image->idempotencyKey='accept-image-'.$tag;reject(fn()=>$service->submit($image,$u),'static image disabled');
// The scheduled job class executes without any browser or GET-driven state transition.
$scheduled=new Espo\\Custom\\Classes\\Jobs\\MediaReconcile($service);$scheduled->run(Espo\\Core\\Job\\Job\\Data::create());
$completed=$service->detail($job['id'],$u);accept($completed['status']==='completed'&&$completed['resultId'],'background completion');
$content=$service->content($completed['resultId'],$u);accept(str_starts_with($content['dataUrl'],'data:video/mp4;base64,'),'private persisted asset');
reject(fn()=>$service->content($completed['resultId'],$other),'other owner content');
$service->reconcile($job['id'],$u);accept($network->downloads===1,'completed reconciliation idempotency');
$network->ambiguous=true;$uncertain=clone $submit;$uncertain->choice=2;$uncertain->idempotencyKey='accept-uncertain-'.$tag;
$pending=$service->submit($uncertain,$u);$service->submit($uncertain,$u);$service->reconcile($pending['id'],$u);
accept($pending['status']==='reconcile_required'&&$network->posts===2,'ambiguous timeout never resubmits');
$record=$em->getEntityById('MediaJob',$pending['id']);$record->set('lastCheckedAt','2000-01-01 00:00:00');$k->save($record);
$service->recover($pending['id'],(object)['providerJobId'=>'recovered-fixture-'.$tag],$u);$scheduled->run(Espo\\Core\\Job\\Job\\Data::create());
accept($service->detail($pending['id'],$u)['status']==='completed'&&$network->posts===2,'manual recovery only queries');
$public=clone $submit;$public->choice=1;$public->textOnly=false;$public->sourceUrl='https://fixture.example/image.png';$public->authorizeSourceTransfer=true;$public->idempotencyKey='accept-public-'.$tag;$network->ambiguous=false;
$service->submit($public,$u);$payload=end($network->payloads);accept(!isset($payload['ratio'])&&$payload['content'][1]['role']==='first_frame','first-frame ratio omitted');
putenv('FUSANHE_MEDIA_MAX_DAILY_JOBS=1');$budget=clone $submit;$budget->idempotencyKey='accept-budget-'.$tag;reject(fn()=>$service->submit($budget,$u),'daily budget');accept($network->posts===3,'budget stops upstream');
putenv('FUSANHE_MEDIA_MAX_DAILY_JOBS=100');putenv('FUSANHE_MEDIA_MAX_ACTIVE_JOBS=1');reject(fn()=>$service->submit($budget,$u),'active budget');accept($network->posts===3,'concurrency stops upstream');
$safe=new Espo\\Custom\\Tools\\Fusanhe\\MediaNetwork();foreach(['http://example.com/a','https://127.0.0.1/a','https://169.254.169.254/a','https://[::1]/a','https://name:pass@example.com/a','https://example.com:8443/a','https://example.com/a#fragment'] as $url)reject(fn()=>$safe->publicUrl($url),'SSRF/url boundary');
echo json_encode(['textCalls'=>$textCalls,'paidPosts'=>$network->posts,'downloads'=>$network->downloads,'completedAsset'=>$completed['resultId']]);
''' % (json.dumps(self.admin_id), json.dumps(self.user_id), json.dumps(self.data_url)))
        self.assertEqual(result['textCalls'], 1)
        self.assertEqual(result['paidPosts'], 3)
        self.assertEqual(result['downloads'], 2)
