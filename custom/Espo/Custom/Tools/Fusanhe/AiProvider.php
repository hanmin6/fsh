<?php
namespace Espo\Custom\Tools\Fusanhe;

final class AiProvider
{
    private const FORBIDDEN = ['price','pricing','moq','minimum order','lead time','delivery time','certificate','certification','payment','discount','compensation','价格','起订量','交期','认证','付款','折扣','赔偿'];
    public function generate(array $context, ?string $choice = null, ?TextGateway $gateway = null): array
    {
        if (!TextGateway::usesNewChannel() && (string) getenv('AI_API_KEY') === '') {
            if ($choice !== null && $choice !== 'legacy') throw new \RuntimeException('text_invalid_choice');
            return $this->mock($context) + ['usageTokens' => null];
        }
        $language = in_array($context['language'] ?? '', ['en', 'zh', 'es', 'fr', 'ar', 'ru', 'pt', 'de'], true) ? $context['language'] : 'en';
        // Only locally derived fixed vocabulary leaves the CRM. Identity, original messages,
        // free-text product names and internal document contents never enter relay prompts.
        $signals = HistorySignals::signals((string) ($context['message'] ?? ''));
        $result = ($gateway ?? new TextGateway())->complete([
            ['role' => 'system', 'content' => 'Draft a concise export-sales reply using only anonymous categorical inquiry signals. Signals indicate a topic was mentioned, never a confirmed requirement. No original customer text, product facts or public approved knowledge is supplied. Do not infer products, amounts, price, MOQ, lead time, certifications, payment, discounts or promises. Ask the customer to clarify details and flag human verification. Return JSON keys intent, summaryZh, suggestedLanguage, draftText, riskLevel, confidence, missingInformation, citedKnowledge. summaryZh and missingInformation must be Chinese. riskLevel medium or high; confidence at most 0.5; citedKnowledge must be empty.'],
            ['role' => 'user', 'content' => json_encode(['signals' => $signals, 'language' => $language], JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR)],
        ], $choice);
        $out = json_decode($result['content'], true);
        if (!is_array($out) || !is_string($out['draftText'] ?? null) || strlen($out['draftText']) > 12000) throw new \RuntimeException('text_invalid_reply');
        foreach (['intent', 'summaryZh', 'suggestedLanguage', 'riskLevel'] as $field) {
            if (!is_string($out[$field] ?? null) || strlen($out[$field]) > 4000) throw new \RuntimeException('text_invalid_reply');
        }
        foreach (['missingInformation', 'citedKnowledge'] as $field) {
            if (!is_array($out[$field] ?? null) || !array_is_list($out[$field]) || count($out[$field]) > 30) throw new \RuntimeException('text_invalid_reply');
            foreach ($out[$field] as $item) if (!is_string($item) || strlen($item) > 2000) throw new \RuntimeException('text_invalid_reply');
        }
        if ($out['citedKnowledge']) throw new \RuntimeException('text_invalid_evidence');
        $out['confidence'] = min(0.5, is_numeric($out['confidence'] ?? null) ? (float) $out['confidence'] : 0.0);
        $out['riskLevel'] = $out['riskLevel'] === 'high' ? 'high' : 'medium';
        $out['missingInformation'][] = '仅基于匿名询盘话题生成，需人工阅读原始消息并核实业务事实。';
        return $this->normalize($out, $result['provider'], $result['model']) + ['usageTokens' => $result['usageTokens']];
    }
    private function mock(array $c): array
    {
        $product=($c['product']??'')?:'the requested product';$hasKnowledge=!empty($c['knowledge']);
        $draft="Dear Customer,\n\nThank you for your inquiry about {$product}. We have received your requirements and will review them with our product team.";
        $missing=[];$risk='low';
        if(!$hasKnowledge){$draft.=" Please allow us to confirm the product specifications before we provide detailed commercial information.";$missing[]='产品规格及商务条款需要人工确认';$risk='medium';}
        $draft.="\n\nCould you please share the required specifications, quantity, destination port and target delivery schedule?\n\nBest regards,\nFusanhe Sales Team";
        return $this->normalize(['intent'=>'产品询盘','summaryZh'=>'客户咨询产品并希望获得进一步信息。','suggestedLanguage'=>($c['language']??'')?:'en','draftText'=>$draft,'riskLevel'=>$risk,'confidence'=>$hasKnowledge?0.82:0.58,'missingInformation'=>$missing,'citedKnowledge'=>array_values(array_filter(array_map(fn($d)=>$d['id']??null,($c['knowledge']??[]))))],'mock','deterministic-mvp');
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
