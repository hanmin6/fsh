<?php
namespace Espo\Core\Exceptions { class BadRequest extends \RuntimeException {} }
namespace {
require 'custom/Espo/Custom/Tools/Fusanhe/MediaNetwork.php';
require 'custom/Espo/Custom/Tools/Fusanhe/MediaGateway.php';
require 'custom/Espo/Custom/Tools/Fusanhe/MediaPolicy.php';
use Espo\Custom\Tools\Fusanhe\MediaNetwork;
use Espo\Custom\Tools\Fusanhe\MediaGateway;
use Espo\Custom\Tools\Fusanhe\MediaPolicy;
function mediaCheck(bool $value, string $test): void { if (!$value) throw new RuntimeException('FAIL: ' . $test); }
function mediaFails(callable $run, string $code): void { try { $run(); } catch (RuntimeException $e) { mediaCheck($e->getMessage() === $code, $code); return; } throw new RuntimeException('Expected: '.$code); }
class FakeMediaNetwork extends MediaNetwork {
    public array $calls=[];
    public array $result=[];
    public bool $fail=false;
    public function json(string $method,string $url,string $key,?array $body=null):array {
        $this->calls[]=[$method,$url,$body];
        mediaCheck($key==='synthetic-media-only','media key isolated');
        if($this->fail)throw new RuntimeException('sensitive upstream credential');
        return $this->result;
    }
    public function publicUrl(string $url):array { if(!str_starts_with($url,'https://public.example.invalid/'))throw new RuntimeException('media_invalid_url');return ['host'=>'public.example.invalid','address'=>'203.0.113.1']; }
    public function download(string $url,string $expectedMime):array {
        mediaCheck($url==='https://public.example.invalid/result.mp4','result url used');
        return ['bytes'=>"\0\0\0\x18ftypmp42synthetic",'mime'=>'video/mp4'];
    }
}
putenv('FUSANHE_MEDIA_API_KEY=synthetic-media-only');putenv('FUSANHE_MEDIA_API_BASE_URL=https://tokendance.space/gateway/v1');putenv('FUSANHE_MEDIA_VIDEO_MODEL=minimax-h3-max');putenv('FUSANHE_MEDIA_ENABLED=true');putenv('FUSANHE_MEDIA_IMAGE_MODEL=seedream-5.0-lite');
$network=new FakeMediaNetwork();$gateway=new MediaGateway($network);
mediaCheck($gateway->status()['capabilities']['video']&&!$gateway->status()['capabilities']['image'],'user image defer enforced');
mediaCheck(!str_contains(json_encode($gateway->status()),'synthetic-media-only'),'status omits credentials');
$preferences=['duration'=>'5','aspect'=>'16:9'];$network->result=['task_id'=>'test-task-123'];
$job=$gateway->submit('video','Synthetic brief','',$preferences,'synthetic-key-123456');
mediaCheck($job['status']==='queued'&&$job['providerJobId']==='test-task-123','task ID persisted');
$call=$network->calls[0];mediaCheck($call[0]==='POST'&&$call[1]==='https://tokendance.space/gateway/minimax/v2/video_generation','documented v2 endpoint');
mediaCheck($call[2]['ratio']==='16:9'&&$call[2]['duration']===5&&$call[2]['resolution']==='768P'&&$call[2]['content'][0]['type']==='text','text video body');
$gateway->submit('video','Synthetic brief','https://public.example.invalid/source.jpg',$preferences,'synthetic-key-123457');
$body=$network->calls[1][2];mediaCheck(!isset($body['ratio'])&&$body['content'][1]['role']==='first_frame'&&$body['content'][1]['image_url']['url']==='https://public.example.invalid/source.jpg','first-frame body, no ratio');
mediaFails(fn()=>$gateway->submit('video','x','data:image/png;base64,x',$preferences,'synthetic-key-123457'),'media_invalid_url');
mediaFails(fn()=>$gateway->submit('image','x','',$preferences,'synthetic-key-123457'),'media_unavailable');
foreach(['queued'=>'queued','running'=>'processing','failed'=>'failed','cancelled'=>'failed','expired'=>'failed'] as $remote=>$local){$network->result=['task'=>['status'=>$remote]];mediaCheck($gateway->reconcile('test-task-123','video')['status']===$local,'provider state '.$remote);}
$network->result=['task'=>['status'=>'succeeded','content'=>['url'=>'https://public.example.invalid/result.mp4']]];
$done=$gateway->reconcile('test-task-123','video');mediaCheck($done['status']==='completed'&&substr($done['bytes'],4,4)==='ftyp','bounded artifact transport');
$network->result=['task'=>['status'=>'unknown']];mediaFails(fn()=>$gateway->reconcile('test-task-123','video'),'media_invalid_response');
$before=count($network->calls);$network->fail=true;mediaFails(fn()=>$gateway->submit('video','x','',$preferences,'synthetic-key-123458'),'sensitive upstream credential');mediaCheck(count($network->calls)===$before+1,'no blind provider retries');
putenv('FUSANHE_MEDIA_VIDEO_MODEL=made-up-media-model');mediaCheck(!$gateway->status()['capabilities']['video'],'unverified alias gated');putenv('FUSANHE_MEDIA_VIDEO_MODEL=minimax-h3-max');
putenv('FUSANHE_MEDIA_API_BASE_URL=https://gw.apimonth.com/v1');mediaCheck(!$gateway->status()['configured'],'wrong channel gated');putenv('FUSANHE_MEDIA_API_BASE_URL=https://tokendance.space/gateway/v1');
$realNetwork=new MediaNetwork();foreach(['http://example.com/a','https://127.0.0.1/a','https://169.254.169.254/a','https://user:pass@example.com/a','https://example.com:8443/a','https://localhost/a','https://2130706433/a','https://[::1]/a'] as $url){mediaFails(fn()=>$realNetwork->publicUrl($url),'media_invalid_url');}
mediaFails(fn()=>MediaPolicy::transition('completed','queued'),'media_invalid_transition');MediaPolicy::transition('submitting','reconcile_required');
mediaFails(fn()=>MediaPolicy::plans('{"plans":[]}'),'creative_invalid_response');
$plans=['plans'=>array_fill(0,3,['name'=>'方案','description'=>'描述','motion'=>'移动','use'=>'展示'])];mediaCheck(count(MediaPolicy::plans(json_encode($plans)))===3,'validated three plans');
mediaFails(fn()=>MediaPolicy::image('data:image/svg+xml;base64,QQ=='),'Choose a PNG, JPEG or WebP image of at most 2 MB.');
echo "Media gateway contracts passed\n";
}
