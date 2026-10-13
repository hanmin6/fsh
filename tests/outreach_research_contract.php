<?php
namespace Espo\Core\Exceptions { class BadRequest extends \RuntimeException {} }
namespace {
require ($argv[1] ?? getcwd() . '/custom/Espo/Custom/Tools/Fusanhe') . '/CustomerRatingPolicy.php';
require ($argv[1] ?? getcwd() . '/custom/Espo/Custom/Tools/Fusanhe') . '/OutreachEvidencePolicy.php';
require ($argv[1] ?? getcwd() . '/custom/Espo/Custom/Tools/Fusanhe') . '/TextGateway.php';

use Espo\Custom\Tools\Fusanhe\OutreachEvidencePolicy as EvidencePolicy;
use Espo\Custom\Tools\Fusanhe\TextGateway;

function checkOutreach(bool $value, string $message): void { if (!$value) throw new RuntimeException($message); }

checkOutreach(EvidencePolicy::sentAt('2026-10-03T08:00:00Z') === '2026-10-03 08:00:00', 'absolute sentAt accepted');
try { EvidencePolicy::sentAt('2026-10-03 08:00:00'); throw new LogicException('timezone-less sentAt accepted'); }
catch (RuntimeException $error) { checkOutreach(!($error instanceof LogicException), 'timezone-less sentAt must be rejected'); }
$snapshot = EvidencePolicy::customerSnapshot(['company' => 'Fixture Foods', 'publicBio' => 'buyer@example.com / +86 138 0013 8000']);
checkOutreach($snapshot['publicBio'] === '[email] / [phone]', 'snapshot contact data must be redacted');

putenv('FUSANHE_TEXT_ENABLED=true');
putenv('FUSANHE_TEXT_API_BASE_URL=https://gateway.example/v1');
putenv('FUSANHE_TEXT_API_KEY=fixture');
putenv('FUSANHE_TEXT_DEFAULT_MODEL=gpt');
putenv('FUSANHE_TEXT_MODEL_GPT=gpt-6.1-sol');
$input = ['customer' => ['name' => 'Fixture Foods'], 'messages' => [], 'asOfUtc' => '2026-10-03T08:00:00Z'];
$data = ['rating' => 'B', 'reason' => '资料有限，存在可跟进的采购线索。', 'confidence' => 'low', 'company' => ['name' => 'Fixture Foods', 'website' => 'https://fixture.example', 'matchStatus' => 'confirmed', 'reason' => '来源与公司名称一致'], 'evidenceMessageIds' => [], 'sourceUrls' => ['https://fixture.example/about', 'https://invented.example'], 'missingInformation' => []];
$transport = static function (string $url, array $payload) use ($data): array {
    checkOutreach($payload['model'] === 'gpt-6.1-sol', 'research uses the authorized search model');
    if (isset($payload['tools'])) return [200, json_encode(['status' => 'completed', 'model' => 'gpt-6.1-sol', 'output' => [['type' => 'web_search_call', 'status' => 'completed', 'action' => ['sources' => [['url' => 'https://fixture.example/about', 'title' => 'Fixture'], ['url' => 'javascript:alert(1)', 'title' => 'Bad']], 'queries' => ['Fixture Foods official']]], ['type' => 'message', 'content' => [['type' => 'output_text', 'text' => '调查完成']]]]])];
    return [200, json_encode([
        'status' => 'completed',
        'model' => 'gpt-6.1-sol',
        'output' => [['content' => [['type' => 'output_text', 'text' => json_encode($data)]]]],
    ])];
};
$result = (new TextGateway($transport))->research($input);
checkOutreach($result['data']['sourceUrls'] === ['https://fixture.example/about'], 'only retrieved source URLs may survive');
try { (new TextGateway(static fn (string $url, array $payload): array => [500, '{}']))->research($input); throw new LogicException('failed research accepted'); }
catch (RuntimeException $error) { checkOutreach($error->getMessage() === 'rating_search_request_failed_http_500', 'gateway failure is observable'); }
putenv('FUSANHE_TEXT_MODEL_GPT=fixture-model');
try { (new TextGateway($transport))->research($input); throw new LogicException('unapproved research model accepted'); }
catch (RuntimeException $error) { checkOutreach($error->getMessage() === 'rating_search_model_unavailable', 'unapproved model is rejected before transport'); }
echo "PASS: outreach timestamp, snapshot redaction, source provenance and gateway failure contract\n";
}
