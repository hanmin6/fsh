<?php
namespace Espo\Custom\Tools\Fusanhe\Connector;

abstract class AbstractPlaceholderConnector implements Connector
{
    abstract protected function channel(): string;
    public function fetchConversations(): array { return []; }
    public function fetchMessages(string $externalConversationId): array { return []; }
    public function acknowledgeMessage(string $externalMessageId): void {}
    public function prepareReply(string $externalConversationId, string $body): array { return compact('externalConversationId', 'body'); }
    public function createOutboundTask(array $preparedReply): array { return ['channel' => $this->channel(), 'preparedReply' => $preparedReply]; }
    public function reportSendResult(string $taskId, array $result): void {}
    public function healthCheck(): array { return ['channel' => $this->channel(), 'configured' => false, 'status' => 'placeholder']; }
}
