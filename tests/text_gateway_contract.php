<?php
require 'custom/Espo/Custom/Tools/Fusanhe/TextGateway.php';
require 'custom/Espo/Custom/Tools/Fusanhe/HistorySignals.php';
require 'custom/Espo/Custom/Tools/Fusanhe/AiProvider.php';
require 'custom/Espo/Custom/Tools/Fusanhe/HistoryAiProvider.php';
use Espo\Custom\Tools\Fusanhe\TextGateway as G;
use Espo\Custom\Tools\Fusanhe\AiProvider as A;
use Espo\Custom\Tools\Fusanhe\HistoryAiProvider as H;

// The minimal lint image lacks mbstring; production Espo provides it.
if (!function_exists('mb_strtolower')) { function mb_strtolower($s) { return strtolower($s); } }
if (!function_exists('mb_strlen')) { function mb_strlen($s) { return strlen($s); } }
function check(bool $ok, string $name): void { if (!$ok) throw new RuntimeException('Contract failed: ' . $name); }
function fails(callable $run, string $expected): void {
    try { $run(); } catch (RuntimeException $e) { check($e->getMessage() === $expected, $expected); return; }
    throw new RuntimeException('Expected failure: ' . $expected);
}
foreach (['API_KEY', 'API_BASE_URL', 'MODEL_GPT', 'MODEL_GROK', 'MODEL_GEMINI', 'DEFAULT_MODEL'] as $field) putenv('FUSANHE_TEXT_' . $field . '=');
putenv('FUSANHE_TEXT_ENABLED=false');
putenv('AI_API_KEY=');
check(!(new G())->status()['available'], 'unconfigured');
check((new A())->generate(['product' => '', 'language' => 'en', 'knowledge' => []])['provider'] === 'mock', 'explicit legacy mock');
putenv('FUSANHE_TEXT_API_BASE_URL=https://text.example.invalid/v1');
putenv('FUSANHE_TEXT_MODEL_GPT=gpt-6.1-sol');
check(!G::usesNewChannel(), 'defaults alone do not enable new channel');
putenv('AI_API_KEY=legacy-test-value');
putenv('FUSANHE_TEXT_ENABLED=true');
putenv('FUSANHE_TEXT_API_BASE_URL=https://text.example.invalid/v1');
putenv('FUSANHE_TEXT_MODEL_GPT=gpt-6.1-sol');
fails(fn () => (new A())->generate([]), 'text_not_configured');
putenv('FUSANHE_TEXT_API_KEY=synthetic-private-test-value');
putenv('FUSANHE_TEXT_MODEL_GROK=grok-4.7');
putenv('FUSANHE_TEXT_MODEL_GEMINI=gemini-3.8-flash');
$status = (new G())->status();
check(!str_contains(json_encode($status), 'synthetic-private-test-value'), 'status omits credential');
check(count($status['models']) === 3 && $status['defaultChoice'] === 'gpt', 'choices');
$calls = [];
$gateway = new G(function ($url, $payload, $key, $timeout) use (&$calls) {
    $calls[] = [$url, $payload];
    check($key === 'synthetic-private-test-value', 'channel isolation');
    $content = '{"ok":true}';
    if (str_ends_with($url, '/responses')) {
        check($payload['store'] === false && $payload['stream'] === false && $payload['text']['format']['type'] === 'json_object', 'responses options');
        return [200, json_encode(['status' => 'completed', 'model' => $payload['model'], 'output' => [['content' => [['type' => 'output_text', 'text' => $content]]]], 'usage' => ['total_tokens' => 36]])];
    }
    check($payload['response_format']['type'] === 'json_object', 'chat options');
    return [200, json_encode(['model' => $payload['model'], 'choices' => [['finish_reason' => 'stop', 'message' => ['content' => $content]]]])];
});
foreach (['gpt', 'grok', 'gemini'] as $choice) {
    $result = $gateway->complete([['role' => 'user', 'content' => 'Synthetic JSON']], $choice);
    check($result['provider'] === 'apimonth', 'provider');
    check($result['usageTokens'] === ($choice === 'gpt' ? 36 : null), 'honest missing usage');
}
check(str_ends_with($calls[0][0], '/responses') && str_ends_with($calls[1][0], '/chat/completions'), 'protocol routing');
fails(fn () => $gateway->complete([['role' => 'user', 'content' => 'JSON']], 'other'), 'text_invalid_choice');
putenv('FUSANHE_TEXT_MODEL_GEMINI=');
fails(fn () => $gateway->complete([['role' => 'user', 'content' => 'JSON']], 'gemini'), 'text_not_configured');
foreach ([401 => 'text_auth_failed', 429 => 'text_rate_limited', 500 => 'text_transport_failed'] as $statusCode => $error) {
    $count = 0;
    $failed = new G(function () use (&$count, $statusCode) { $count++; return [$statusCode, 'upstream credential and private error']; });
    fails(fn () => $failed->complete([['role' => 'user', 'content' => 'JSON']], 'grok'), $error);
    check($count === 1, 'no automatic paid retries');
}
fails(fn () => (new G(fn () => throw new RuntimeException('sensitive transport detail')))->complete([['role' => 'user', 'content' => 'JSON']], 'grok'), 'text_transport_failed');
fails(fn () => (new G(fn () => [200, str_repeat('x', 262145)]))->complete([['role' => 'user', 'content' => 'JSON']], 'grok'), 'text_response_too_large');
fails(fn () => (new G(fn () => [200, '{"status":"incomplete","output":[]}']))->complete([['role' => 'user', 'content' => 'JSON']], 'gpt'), 'text_incomplete_response');
fails(fn () => (new G(fn () => [200, '{"choices":[{"message":{"content":"not JSON"}}]}']))->complete([['role' => 'user', 'content' => 'JSON']], 'grok'), 'text_invalid_json');
fails(fn () => (new G(fn () => [200, '{"choices":[{"message":{"content":"{}"}}]}']))->complete([['role' => 'user', 'content' => 'JSON']], 'grok'), 'text_invalid_response');
fails(fn () => (new G(fn () => [200, '{"model":"unrequested-model","choices":[{"message":{"content":"{}"}}]}']))->complete([['role' => 'user', 'content' => 'JSON']], 'grok'), 'text_model_mismatch');
fails(fn () => (new G(fn () => [200, '{"model":"unrequested-model","status":"completed","output":[{"content":[{"type":"output_text","text":"{}"}]}]}']))->complete([['role' => 'user', 'content' => 'JSON']], 'gpt'), 'text_model_mismatch');
$unknownUsage = (new G(fn () => [200, '{"model":"grok-4.7","choices":[{"message":{"content":"{}"}}],"usage":{"total_tokens":"unknown"}}']))->complete([['role' => 'user', 'content' => 'JSON']], 'grok');
check($unknownUsage['usageTokens'] === null, 'unknown usage remains null');
$fingerprint = $gateway->fingerprint();
putenv('FUSANHE_TEXT_DEFAULT_MODEL=grok');
check($fingerprint !== $gateway->fingerprint(), 'cache tracks selected model');
putenv('FUSANHE_TEXT_API_BASE_URL=https://name:pass@text.example.invalid/v1');
check(!$gateway->status()['configured'], 'credential URL rejected');
putenv('FUSANHE_TEXT_API_BASE_URL=https://text.example.invalid/v1');
$reply = ['intent' => '询盘', 'summaryZh' => '话题待核实', 'suggestedLanguage' => 'en', 'draftText' => 'Could you clarify your requirements?', 'riskLevel' => 'low', 'confidence' => 0.9, 'missingInformation' => [], 'citedKnowledge' => []];
$replyGateway = new G(function ($url, $payload) use ($reply) {
    $sent = json_encode($payload);
    check(!str_contains($sent, 'fixture@example.invalid') && !str_contains($sent, 'PRIVATE_NAME') && !str_contains($sent, 'PRIVATE_PRODUCT') && !str_contains($sent, 'PRIVATE_DOC'), 'reply anonymization');
    check(str_contains($sent, 'price_question'), 'derived signal');
    return [200, json_encode(['model' => 'grok-4.7', 'choices' => [['message' => ['content' => json_encode($reply)]]], 'usage' => ['total_tokens' => 12]])];
});
$result = (new A())->generate(['message' => 'PRIVATE_NAME fixture@example.invalid asks price', 'history' => [['body' => 'private-history']], 'customer' => ['displayName' => 'PRIVATE_NAME'], 'product' => 'PRIVATE_PRODUCT', 'language' => 'en', 'knowledge' => [['id' => 'doc', 'text' => 'PRIVATE_DOC']]], 'grok', $replyGateway);
check($result['riskLevel'] === 'medium' && $result['confidence'] === 0.5 && $result['usageTokens'] === 12, 'cautious reply provenance');
$history = ['summaryZh' => '待确认', 'demand' => '待确认', 'historyProgress' => '待确认', 'latestStatus' => '待确认', 'nextAction' => '人工核对', 'products' => [], 'buyingSignals' => [], 'risks' => [], 'missingFacts' => [], 'evidenceMessageIds' => ['m1']];
$historyGateway = new G(function ($url, $payload) use ($history) {
    check(!str_contains(json_encode($payload), 'PRIVATE_SOURCE'), 'history drops unknown/raw fields');
    return [200, json_encode(['model' => 'grok-4.7', 'choices' => [['message' => ['content' => json_encode($history)]]], 'usage' => ['total_tokens' => 19]])];
});
$out = (new H())->analyze(['source' => 'PRIVATE_SOURCE', 'messageCounts' => ['inbound' => 3], 'evidence' => [['ref' => 'm1', 'direction' => 'inbound', 'signals' => ['price_question', 'PRIVATE_SOURCE'], 'occurrences' => 2, 'body' => 'PRIVATE_SOURCE']]], $historyGateway);
check($out['provider'] === 'apimonth' && $out['usageTokens'] === 19 && $out['evidenceMessageIds'] === ['m1'], 'history provenance');
echo "Text gateway contracts passed\n";
