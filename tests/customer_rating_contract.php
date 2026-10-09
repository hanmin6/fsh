<?php
require $argv[1] . '/CustomerRatingPolicy.php';
require $argv[1] . '/TextGateway.php';
use Espo\Custom\Tools\Fusanhe\CustomerRatingPolicy as Policy;
use Espo\Custom\Tools\Fusanhe\TextGateway;
function check($value,$message){if(!$value)throw new RuntimeException($message);}
$input=['customer'=>['name'=>'Buyer','accountName'=>'Acme Foods','website'=>'https://acme.example'],'messages'=>[['id'=>'m1','body'=>'Please quote 5 pallets.']]];
$data=['rating'=>'A','reason'=>'有具体产品询价和采购数量，但交期及付款条件尚未确认。','confidence'=>'medium','company'=>['name'=>'Acme Foods','website'=>'https://acme.example','matchStatus'=>'confirmed','reason'=>'公司名及官网对应'],'evidenceMessageIds'=>['m1'],'sourceUrls'=>['https://acme.example/about'],'missingInformation'=>['交期']];
$sources=[['url'=>'https://acme.example/about','title'=>'Acme']];
$r=Policy::validate($data,$input,$sources);check($r['label']==='高'&&$r['company']['matchStatus']==='confirmed','verified company accepted');
$r=Policy::validate($data,$input,[]);check($r['company']['matchStatus']==='possible'&&$r['sourceUrls']===[],'invented sources discarded');
$unknown=$input;$unknown['customer']=['name'=>'Common Name'];$r=Policy::validate($data,$unknown,$sources);check($r['company']['matchStatus']==='possible','name-only match cannot confirm company');
foreach (['rating'=>'X','evidenceMessageIds'=>['invented']] as $k=>$v){try{Policy::validate(array_merge($data,[$k=>$v]),$input,$sources);throw new LogicException('accepted invalid '.$k);}catch(RuntimeException $e){check(!($e instanceof LogicException),'bad validation');}}
putenv('FUSANHE_TEXT_ENABLED=true');putenv('FUSANHE_TEXT_API_BASE_URL=https://gateway.example/v1');putenv('FUSANHE_TEXT_API_KEY=test');putenv('FUSANHE_TEXT_DEFAULT_MODEL=gpt');putenv('FUSANHE_TEXT_MODEL_GPT=fixture-model');
$transport=function($url,$payload)use($data,$sources){if (!isset($payload['tools'])) return [200,json_encode(['status'=>'completed','model'=>'fixture-model','output'=>[['content'=>[['type'=>'output_text','text'=>json_encode($data)]]]],'usage'=>['total_tokens'=>40]])];check($payload['tools'][0]['type']==='web_search','web search required');return [200,json_encode(['status'=>'completed','model'=>'fixture-model','output'=>[['type'=>'web_search_call','status'=>'completed','action'=>['sources'=>$sources,'queries'=>['Acme Foods official']]],['type'=>'message','content'=>[['type'=>'output_text','text'=>json_encode($data)]]]],'usage'=>['total_tokens'=>100]])];};
$r=(new TextGateway($transport))->research($input);check($r['data']['rating']==='A'&&count($r['data']['sources'])===1,'research provenance retained');
try{(new TextGateway(fn()=>[200,json_encode(['status'=>'completed','model'=>'fixture-model','output'=>[['content'=>[['type'=>'output_text','text'=>json_encode($data)]]]]])]))->research($input);throw new LogicException('accepted no web call');}catch(RuntimeException $e){check($e->getMessage()==='rating_web_search_not_executed','must observe actual web retrieval');}
echo "PASS: rating scale, exact evidence IDs, company ambiguity, invented URLs, gateway web-search provenance\n";
