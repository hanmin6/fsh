<?php
namespace Espo\Custom\Tools\Fusanhe\Connector;

final class AlibabaConnector extends AbstractPlaceholderConnector
{
    protected function channel(): string
    {
        return 'Alibaba';
    }

    public function healthCheck(): array
    {
        $baseUrl = rtrim((string) (getenv('ALIBABA_BRIDGE_URL') ?: 'https://api.fsh.digital'), '/');
        $token = trim((string) getenv('ALIBABA_BRIDGE_TOKEN'));

        if ($token === '') {
            return [
                'channel' => 'Alibaba',
                'configured' => false,
                'status' => 'unknown',
                'error' => 'ALIBABA_BRIDGE_TOKEN is not configured',
                'lastCheckedAt' => gmdate('Y-m-d H:i:s'),
            ];
        }

        $statusUrl = $baseUrl . '/alibaba/channel/status';

        $ch = curl_init($statusUrl);
        if ($ch === false) {
            return [
                'channel' => 'Alibaba',
                'configured' => true,
                'status' => 'offline',
                'error' => 'curl_init failed',
                'lastCheckedAt' => gmdate('Y-m-d H:i:s'),
            ];
        }

        $headers = [
            'Accept: application/json',
            'User-Agent: FusanheCRM-Connector/1.0',
        ];
        if ($token !== '') {
            $headers[] = 'Authorization: Bearer ' . $token;
        }

        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_HTTPHEADER => $headers,
            CURLOPT_CONNECTTIMEOUT => 5,
            CURLOPT_TIMEOUT => 10,
            CURLOPT_SSL_VERIFYPEER => true,
            CURLOPT_SSL_VERIFYHOST => 2,
        ]);

        $response = curl_exec($ch);
        $httpCode = (int) curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
        $curlError = curl_error($ch);
        curl_close($ch);

        if ($curlError !== '' || !is_string($response) || $response === '') {
            return [
                'channel' => 'Alibaba',
                'configured' => true,
                'status' => 'offline',
                'error' => $curlError ?: 'Empty response from bridge',
                'endpoint' => $statusUrl,
                'lastCheckedAt' => gmdate('Y-m-d H:i:s'),
            ];
        }

        $data = json_decode($response, true);
        if ($httpCode !== 200 || !is_array($data) || !($data['ok'] ?? false)) {
            return [
                'channel' => 'Alibaba',
                'configured' => true,
                'status' => 'degraded',
                'httpCode' => $httpCode,
                'error' => $data['error'] ?? 'Bridge returned error',
                'lastCheckedAt' => gmdate('Y-m-d H:i:s'),
            ];
        }

        $status = (string) ($data['status'] ?? 'healthy');
        return [
            'channel' => 'Alibaba',
            'configured' => true,
            'status' => $status,
            'connected' => (bool) ($data['connected'] ?? false),
            'account' => $data['account'] ?? null,
            'sellerId' => $data['sellerId'] ?? null,
            'savedAt' => $data['savedAt'] ?? null,
            'expireTime' => $data['expireTime'] ?? null,
            'expiresInSeconds' => $data['expiresInSeconds'] ?? null,
            'isExpired' => (bool) ($data['isExpired'] ?? false),
            'appKey' => $data['appKey'] ?? null,
            'lastCheckedAt' => gmdate('Y-m-d H:i:s'),
        ];
    }

    public function prepareReply(string $externalConversationId, string $body): array
    {
        return [
            'channel' => 'Alibaba',
            'externalConversationId' => $externalConversationId,
            'body' => $body,
            'targetPlatform' => 'ICBU',
            'preparedAt' => gmdate('Y-m-d H:i:s'),
        ];
    }

    public function createOutboundTask(array $preparedReply): array
    {
        return [
            'channel' => 'Alibaba',
            'action' => 'send_message',
            'preparedReply' => $preparedReply,
            'platform' => 'ICBU',
        ];
    }

}
