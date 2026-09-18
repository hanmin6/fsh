<?php
namespace Espo\Custom\Tools\Fusanhe\Connector;
final class MockConnector extends AbstractPlaceholderConnector
{
    protected function channel(): string { return 'Mock'; }
    public function fetchConversations(): array { return [['externalId' => 'ALI-DEMO-001', 'subject' => 'Hydraulic fitting inquiry']]; }
    public function fetchMessages(string $externalConversationId): array { return [['externalId' => 'MSG-DEMO-001', 'body' => 'Could you send specifications for your stainless steel hydraulic fittings?']]; }
    public function healthCheck(): array { return ['channel' => 'Mock', 'configured' => true, 'status' => 'healthy']; }
}
