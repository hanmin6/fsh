<?php
namespace Espo\Custom\Tools\Fusanhe;

/** Model selects from approved intake responses; it cannot invent business commitments. */
final class ReceptionReply
{
    public function __construct(private ?TextGateway $gateway = null) {}
    public const VERSION = 'scheduled-intake-v1';
    private const REPLIES = [
        'general' => ['en' => 'Thank you for contacting Fusanhe. I am the AI reception assistant. Could you share the product, specifications, quantity and destination you need? Our sales team will review the details when business hours resume.', 'zh' => '您好，我是福三和 AI 接待助手。请告诉我您需要的产品、规格、数量和目的地，我们的销售同事将在工作时间继续跟进。'],
        'price' => ['en' => 'Thank you for your quotation inquiry. I am the Fusanhe AI reception assistant. Could you share the product, specifications, quantity and destination? Pricing requires confirmation by our sales team during business hours.', 'zh' => '您好，我是福三和 AI 接待助手。收到您的报价咨询，请补充产品、规格、数量和目的地，价格需由销售同事在工作时间确认。'],
        'sample' => ['en' => 'Thank you for your sample inquiry. I am the Fusanhe AI reception assistant. Which product and specifications are you interested in, and where would the sample be needed? Our sales team will confirm sample arrangements during business hours.', 'zh' => '您好，我是福三和 AI 接待助手。请告诉我您需要的样品、规格和收件地区，样品安排将由销售同事在工作时间确认。'],
        'specification' => ['en' => 'Thank you for your product inquiry. I am the Fusanhe AI reception assistant. Could you share the product, application and specifications you require? Our sales team will verify the product details during business hours.', 'zh' => '您好，我是福三和 AI 接待助手。请补充产品名称、用途和所需规格，产品信息将由销售同事在工作时间核实。'],
        'delivery' => ['en' => 'Thank you for your shipping inquiry. I am the Fusanhe AI reception assistant. Could you share the product, quantity, destination and requested delivery date? Our sales team will confirm feasibility during business hours.', 'zh' => '您好，我是福三和 AI 接待助手。请补充产品、数量、目的地和期望交付日期，是否可安排将由销售同事在工作时间确认。'],
        'certificate' => ['en' => 'Thank you for your certification inquiry. I am the Fusanhe AI reception assistant. Could you share the product, destination market and standards you require? Our sales team will verify the applicable documents during business hours.', 'zh' => '您好，我是福三和 AI 接待助手。请告诉我相关产品、目标市场和所需标准，适用证书将由销售同事在工作时间核实。'],
    ];
    public function generate(string $message, string $language, ?TextGateway $gateway = null): array
    {
        $gateway = $gateway ?? $this->gateway ?? new TextGateway();
        $selected = array_values(array_filter($gateway->status()['models'], fn ($m) => $m['choice'] === 'gpt'));
        if (!TextGateway::usesNewChannel() || empty($selected[0]['available']) || $selected[0]['model'] !== 'gpt-6.1-sol') throw new \RuntimeException('reception_model_unavailable');
        $result = $gateway->complete([
            ['role' => 'system', 'content' => 'Select an intake response for anonymous inquiry topic signals. Return JSON with only replyKey. Valid replyKey values: general, price, sample, specification, delivery, certificate. Signals indicate topics, never confirmed facts. Use general if none match.'],
            ['role' => 'user', 'content' => json_encode(['signals' => HistorySignals::signals($message)], JSON_THROW_ON_ERROR)],
        ], 'gpt', true);
        if ($result['model'] !== 'gpt-6.1-sol') throw new \RuntimeException('reception_model_mismatch');
        $selection = json_decode($result['content'], true);
        $key = $selection['replyKey'] ?? null;
        if (!is_string($key) || !isset(self::REPLIES[$key])) throw new \RuntimeException('reception_invalid_selection');
        return ['text' => self::REPLIES[$key][$language === 'zh' ? 'zh' : 'en'], 'replyKey' => $key,
            'provider' => $result['provider'], 'model' => $result['model'], 'usageTokens' => $result['usageTokens'] ?? null];
    }
}
