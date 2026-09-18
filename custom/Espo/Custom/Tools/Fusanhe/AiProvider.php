<?php
namespace Espo\Custom\Tools\Fusanhe;

final class AiProvider
{
    private const FORBIDDEN = ['price','pricing','moq','minimum order','lead time','delivery time','certificate','certification','payment','discount','compensation','价格','起订量','交期','认证','付款','折扣','赔偿'];
    public function generate(array $context): array
    {
        $key=(string)getenv('AI_API_KEY');
        if($key==='') return $this->mock($context);
        $url=rtrim((string)(getenv('AI_API_BASE_URL')?:'https://api.openai.com/v1'),'/').'/chat/completions';
        $payload=['model'=>(string)(getenv('AI_MODEL')?:'gpt-4.1-mini'),'response_format'=>['type'=>'json_object'],'messages'=>[
            ['role'=>'system','content'=>'You draft concise export-sales replies. Use only supplied approved knowledge. Never invent price, MOQ, lead time, certifications, payment, discounts, quality or compensation promises. Return JSON keys intent, summaryZh, suggestedLanguage, draftText, riskLevel, confidence, missingInformation, citedKnowledge.'],
            ['role'=>'user','content'=>json_encode($context,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES)]
        ]];
        $raw=false;$code=0;$error='';$maxRetries=max(0,(int)(getenv('AI_MAX_RETRIES')?:2));
        for($attempt=0;$attempt<=$maxRetries;$attempt++){
            $ch=curl_init($url); curl_setopt_array($ch,[CURLOPT_RETURNTRANSFER=>true,CURLOPT_POST=>true,CURLOPT_HTTPHEADER=>['Authorization: Bearer '.$key,'Content-Type: application/json'],CURLOPT_POSTFIELDS=>json_encode($payload),CURLOPT_TIMEOUT=>(int)(getenv('AI_TIMEOUT')?:30)]);
            $raw=curl_exec($ch);$code=(int)curl_getinfo($ch,CURLINFO_RESPONSE_CODE);$error=curl_error($ch);curl_close($ch);
            if($code>=200&&$code<300&&is_string($raw))break;
            if($attempt<$maxRetries)usleep((int)(250000*(2**$attempt)));
        }
        if($code<200||$code>=300||!is_string($raw)) throw new \RuntimeException('AI API failed: '.($error?:'HTTP '.$code));
        $decoded=json_decode($raw,true);$out=json_decode($decoded['choices'][0]['message']['content']??'',true);
        if(!is_array($out)) throw new \RuntimeException('AI API returned invalid JSON.');
        return $this->normalize($out,'openai-compatible',(string)$payload['model']);
    }
    private function mock(array $c): array
    {
        $product=$c['product']?:'the requested product';$hasKnowledge=!empty($c['knowledge']);
        $draft="Dear Customer,\n\nThank you for your inquiry about {$product}. We have received your requirements and will review them with our product team.";
        $missing=[];$risk='low';
        if(!$hasKnowledge){$draft.=" Please allow us to confirm the product specifications before we provide detailed commercial information.";$missing[]='产品规格及商务条款需要人工确认';$risk='medium';}
        $draft.="\n\nCould you please share the required specifications, quantity, destination port and target delivery schedule?\n\nBest regards,\nFusanhe Sales Team";
        return $this->normalize(['intent'=>'产品询盘','summaryZh'=>'客户咨询产品并希望获得进一步信息。','suggestedLanguage'=>$c['language']?:'en','draftText'=>$draft,'riskLevel'=>$risk,'confidence'=>$hasKnowledge?0.82:0.58,'missingInformation'=>$missing,'citedKnowledge'=>array_values(array_filter(array_map(fn($d)=>$d['id']??null,$c['knowledge'])))],'mock','deterministic-mvp');
    }
    private function normalize(array $out,string $provider,string $model): array
    {
        $text=trim((string)($out['draftText']??'')); if($text==='') throw new \RuntimeException('AI reply is empty.');
        $risk=(string)($out['riskLevel']??'medium'); if(!in_array($risk,['low','medium','high'],true))$risk='medium';
        if($this->containsUnsupportedClaim($text) && empty($out['citedKnowledge'])){$risk='high';$out['missingInformation'][]='商务承诺缺少已审核知识依据，需要人工确认';}
        return ['intent'=>(string)($out['intent']??'未知'),'summaryZh'=>(string)($out['summaryZh']??''),'suggestedLanguage'=>(string)($out['suggestedLanguage']??'en'),'draftText'=>$text,'riskLevel'=>$risk,'confidence'=>max(0,min(1,(float)($out['confidence']??0.5))),'missingInformation'=>array_values((array)($out['missingInformation']??[])),'citedKnowledge'=>array_values((array)($out['citedKnowledge']??[])),'provider'=>$provider,'model'=>$model];
    }
    private function containsUnsupportedClaim(string $text): bool { $lower=mb_strtolower($text);foreach(self::FORBIDDEN as $term)if(str_contains($lower,$term))return true;return false; }
}
