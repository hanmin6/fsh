<?php
namespace Espo\Custom\Tools\Fusanhe\Connector;

interface Connector
{
    public function fetchConversations(): array;
    public function fetchMessages(string $externalConversationId): array;
    public function acknowledgeMessage(string $externalMessageId): void;
    public function prepareReply(string $externalConversationId, string $body): array;
    public function createOutboundTask(array $preparedReply): array;
    public function reportSendResult(string $taskId, array $result): void;
    public function healthCheck(): array;
}
