<?php
// Synthetic-only behavior tests, no framework/database/model credentials needed.
require __DIR__ . '/../../custom/Espo/Custom/Tools/Fusanhe/ReplyAssistant.php';
use Espo\Custom\Tools\Fusanhe\ReplyAssistant;
class FixtureAssistant extends ReplyAssistant {
    public array $output = [];
    public array $payload = [];
    protected function complete(array $messages): array { $this->payload = $messages; return $this->output; }
}
function check(bool $condition, string $label): void { if (!$condition) throw new RuntimeException($label); }
function fails(callable $fn, string $type): void {
    try { $fn(); } catch (Throwable $e) { check($e instanceof $type, 'wrong exception: ' . get_class($e)); return; }
    throw new RuntimeException('Expected ' . $type);
}
$service = new FixtureAssistant();
$analysis = ['recognizedText'=>'Customer: Can you share packaging options?', 'summaryZh'=>'客户咨询包装', 'language'=>'en', 'directions'=>[
    ['title'=>'确认需求','description'=>'询问包装和采购数量'],['title'=>'介绍选项','description'=>'先确认可选包装'],['title'=>'了解用途','description'=>'了解客户应用场景']
], 'warnings'=>[]];
$service->output = $analysis;
$result = $service->handle(['operation'=>'analyze','text'=>'Synthetic customer question']);
check(count($result['directions']) === 3 && $result['directions'][0]['id'] === 'direction-1', 'directions');
check(str_contains($service->payload[0]['content'], 'untrusted'), 'prompt boundary');
$png = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=';
$service->handle(['operation'=>'analyze','images'=>[$png]]);
check($service->payload[1]['content'][1]['type'] === 'input_image', 'vision content');
fails(fn()=>$service->handle(['operation'=>'analyze']), InvalidArgumentException::class);
fails(fn()=>$service->handle(['operation'=>'analyze','images'=>array_fill(0,4,$png)]), InvalidArgumentException::class);
fails(fn()=>$service->handle(['operation'=>'analyze','images'=>['https://example.test/image.png']]), InvalidArgumentException::class);
fails(fn()=>$service->handle(['operation'=>'analyze','images'=>['data:image/png;base64,'.base64_encode('not an image')]]), InvalidArgumentException::class);
fails(fn()=>$service->handle(['operation'=>'analyze','images'=>[str_replace('image/png','image/jpeg',$png)]]), InvalidArgumentException::class);
fails(fn()=>$service->handle(['operation'=>'analyze','text'=>str_repeat('a',12001)]), InvalidArgumentException::class);
fails(fn()=>$service->handle(['operation'=>'generate','text'=>'hello']), InvalidArgumentException::class);
fails(fn()=>$service->handle(['operation'=>'generate','text'=>'hello','customInstruction'=>'reply','language'=>'invalid']), InvalidArgumentException::class);
$service->output = ['recognizedText'=>'','summaryZh'=>'无法识别','language'=>'en','directions'=>[],'warnings'=>[]];
$result = $service->handle(['operation'=>'analyze','images'=>[$png]]);
check(count($result['warnings']) > 0 && $result['directions'] === [], 'unreadable image');
$service->output = $analysis;
$service->output['directions'] = array_slice($analysis['directions'],0,2);
fails(fn()=>$service->handle(['operation'=>'analyze','text'=>'hi']), UnexpectedValueException::class);
$service->output = ['draftText'=>'Could you share the required quantity?', 'translationZh'=>'请问您需要的数量？','missingInformation'=>['规格待确认'],'conflictNote'=>''];
$result = $service->handle(['operation'=>'generate','text'=>'hello','customInstruction'=>'先问数量','language'=>'en']);
check($result['draftText'] === $service->output['draftText'], 'custom-only generation');
$service->handle(['operation'=>'generate','text'=>'hello','direction'=>['title'=>'询问需求','description'=>'确认包装'],'customInstruction'=>'不要问包装','language'=>'auto','currentDraft'=>'edited draft','refinement'=>'shorter']);
check(str_contains($service->payload[1]['content'][0]['text'], 'edited draft'), 'refinement uses current edited draft');
check(!str_contains(json_encode($service->payload), 'data:image'), 'no screenshot repeated on generation');
$service->output['translationZh'] = [];
fails(fn()=>$service->handle(['operation'=>'generate','text'=>'hi','customInstruction'=>'reply']), UnexpectedValueException::class);
putenv('AI_API_KEY=');
putenv('FUSANHE_TEXT_API_KEY=');
putenv('FUSANHE_TEXT_ENABLED=false');
fails(fn()=>(new ReplyAssistant())->handle(['operation'=>'analyze','text'=>'hi']), RuntimeException::class);
echo "Reply assistant behavior checks passed\n";

putenv('FUSANHE_TEXT_ENABLED=true');
putenv('FUSANHE_TEXT_API_KEY=synthetic-key');
putenv('FUSANHE_TEXT_API_BASE_URL=https://gateway.example.test/v1');
putenv('AI_MODEL=wrong-model');
putenv('FUSANHE_TEXT_MODEL_GPT=wrong-model');
$model = ReplyAssistant::MODEL;
$status = 'completed';
$transport = function($url, $payload, $key, $timeout) use (&$model, &$status, $analysis, $png) {
    check($url === 'https://gateway.example.test/v1/responses', 'Responses endpoint');
    check($payload['model'] === 'gpt-6.1-sol', 'fixed model');
    check($payload['store'] === false && $payload['stream'] === false, 'ephemeral response');
    check($payload['text']['format']['type'] === 'json_object', 'JSON format');
    check($payload['input'][1]['content'][1]['image_url'] === $png, 'Responses image data');
    check($payload['input'][1]['content'][0]['type'] === 'input_text', 'Responses text');
    return [200, json_encode(['status'=>$status, 'model'=>$model, 'output'=>[['content'=>[['type'=>'output_text','text'=>json_encode($analysis)]]]]])];
};
$service = new ReplyAssistant($transport);
$service->handle(['operation'=>'analyze','images'=>[$png]]);
$model = 'substitute-model';
fails(fn()=>$service->handle(['operation'=>'analyze','images'=>[$png]]), UnexpectedValueException::class);
$model = ReplyAssistant::MODEL; $status = 'incomplete';
fails(fn()=>$service->handle(['operation'=>'analyze','images'=>[$png]]), UnexpectedValueException::class);
putenv('FUSANHE_TEXT_API_BASE_URL=http://gateway.example.test/v1');
fails(fn()=>$service->handle(['operation'=>'analyze','images'=>[$png]]), RuntimeException::class);
echo "Fixed GPT-6.1 Sol Responses protocol checks passed\n";
