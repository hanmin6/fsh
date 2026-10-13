<?php
namespace Espo\Custom\Tools\Fusanhe;

use Espo\Core\InjectableFactory;
use Espo\Core\Mail\Account\PersonalAccount\AccountFactory;
use Espo\Core\Mail\Importer\Data;
use Espo\Core\Mail\Importer\DefaultImporter;
use Espo\Core\Mail\MessageWrapper;
use Espo\Core\Mail\ParserFactory;
use Espo\Entities\Email;
use Espo\ORM\EntityManager;
use RuntimeException;

/** Imports the operator's own Zoho mailbox without IMAP or an outbound executor. */
final class ZohoMailImporter
{
    public function __construct(
        private EntityManager $em,
        private InjectableFactory $factory,
        private WorkflowService $workflow,
        private ServiceKernel $kernel,
        private IdentityService $identities,
        private SalesService $sales,
    ) {}

    public function import(array $input): array
    {
        $account = $this->factory->create(AccountFactory::class)->create((string) $input['emailAccountId']);
        $entity = $account->getEntity();
        if (!$entity->isActive()) {
            throw new RuntimeException('CRM mailbox is disabled.');
        }
        $mailbox = strtolower((string) $entity->getEmailAddress());
        if ($mailbox !== strtolower((string) ($input['mailbox'] ?? ''))) {
            throw new RuntimeException('Mailbox does not match the configured CRM account.');
        }
        $owner = $entity->getAssignedUser()->getId();
        $data = Data::create()->withAssignedUserId($owner)->withUserIdList([$owner]);
        $parser = $this->factory->create(ParserFactory::class)->create();
        $importer = $this->factory->create(DefaultImporter::class);
        $results = [];

        foreach ($input['messages'] ?? [] as $item) {
            $externalId = (string) ($item['messageExternalId'] ?? '');
            if (!str_starts_with($externalId, 'zoho:') || empty($item['rawMime'])) {
                throw new RuntimeException('Invalid Zoho source message.');
            }
            $message = new MessageWrapper(0, parser: $parser, fullRawContent: (string) $item['rawMime']);
            $existing = $this->em->getRDBRepository('ExternalMessage')
                ->where(['externalId' => $externalId])->findOne();
            if ($existing && !empty(((array) $existing->get('rawPayload'))['nativeEmailId'])) {
                $existingMetadata = (array) ($existing->get('rawPayload') ?? []);
                $nativeEmail = $this->em->getEntityById('Email', $existingMetadata['nativeEmailId']);
                if ($nativeEmail) {
                    $this->stamp($existing, $nativeEmail, $parser->getHeader($message, 'Date'));
                }
                $results[] = ['sourceId' => $externalId, 'deduplicated' => true,
                    'messageId' => $existing->getId(),
                    'nativeEmailId' => $existingMetadata['nativeEmailId'] ?? null];
                continue;
            }
            $email = $importer->import($message, $data);
            if (!$email) {
                // The native importer skips its own already-stored outgoing mail.
                $email = $this->em->getRDBRepository('Email')
                    ->where(['messageId' => (string) ($item['rfcMessageId'] ?? '')])->findOne();
            }
            if (!$email) {
                throw new RuntimeException('Native email import returned no record.');
            }
            $account->relateEmail($email);
            $isOutbound = strtolower((string) $email->getFromAddress()) === $mailbox;
            $salesHeaders = ['autoSubmitted' => $parser->getHeader($message, 'Auto-Submitted'),
                'references' => $parser->getHeader($message, 'References'), 'inReplyTo' => $parser->getHeader($message, 'In-Reply-To')];
            if ($isOutbound && ($salesMessage = $this->em->getRDBRepository('ExternalMessage')->where(['externalId' => 'sales-email:' . $email->getId()])->findOne())) {
                $email->setStatus(Email::STATUS_SENT);
                $rawDate = $parser->getHeader($message, 'Date');
                if ($rawDate && ($timestamp = strtotime($rawDate)) !== false) $email->setDateSent(\Espo\Core\Field\DateTime::fromString(gmdate('Y-m-d H:i:s', $timestamp)));
                $this->kernel->save($email);
                $this->sales->receive($salesMessage, $email, $salesHeaders);
                $results[] = ['sourceId' => $externalId, 'nativeEmailId' => $email->getId(), 'messageId' => $salesMessage->getId(), 'deduplicated' => true];
                continue;
            }
            if ($isOutbound && $email->getStatus() !== Email::STATUS_SENT) {
                $email->setStatus(Email::STATUS_SENT);
                $this->em->saveEntity($email, ['silent' => true]);
            }
            $body = trim((string) $email->getBodyPlain());
            if ($body === '') {
                $body = $email->getSubject() ?: '附件邮件，请在 CRM 邮箱中查看原文。';
            }
            $sentAt = $email->getDateSent()?->toString() ?? $this->kernel->now();
            $sender = $isOutbound ? (string) ($item['correspondent'] ?? '') : (string) $email->getFromAddress();
            $channel = $this->channel($mailbox);
            $thread = (string) $item['conversationExternalId'];
            $conversation = $this->em->getRDBRepository('ExternalConversation')
                ->where(['channelId' => $channel->getId(), 'externalId' => $thread])->findOne();
            $previous = $conversation ? [
                'lastMessageAt' => $conversation->get('lastMessageAt'),
                'lastInboundAt' => $conversation->get('lastInboundAt'),
                'lastMessagePreview' => $conversation->get('lastMessagePreview'),
            ] : [];
            $metadata = ['source' => 'Zoho Mail API', 'nativeEmailId' => $email->getId(),
                'zohoMessageId' => (string) $item['zohoMessageId'], 'folderId' => (string) $item['folderId']];

            if (!$isOutbound) {
                $result = $this->workflow->intake((object) [
                    'channelType' => 'Email', 'accountHandle' => $mailbox,
                    'conversationExternalId' => $thread, 'messageExternalId' => $externalId,
                    'externalUserId' => $sender, 'email' => $sender,
                    'senderName' => (string) ($item['senderName'] ?? $sender),
                    'subject' => (string) $email->getSubject(), 'body' => $body, 'sentAt' => $sentAt,
                ]);
                $external = $this->em->getEntityById('ExternalMessage', $result['messageId']);
                $external->set('rawPayload', $metadata);
                $this->kernel->save($external);
                $conversation = $this->em->getEntityById('ExternalConversation', $result['conversationId']);
                // Moving an older email into Inbox must not rewind a newer conversation.
                if (($previous['lastMessageAt'] ?? '') > $sentAt) {
                    $conversation->set('lastMessageAt', $previous['lastMessageAt']);
                    $conversation->set('lastMessagePreview', $previous['lastMessagePreview']);
                }
                if (($previous['lastInboundAt'] ?? '') > $sentAt) {
                    $conversation->set('lastInboundAt', $previous['lastInboundAt']);
                }
                $this->kernel->save($conversation);
            } else {
                if (!$conversation) {
                    [$identity] = $this->identities->resolveIdentity('Email', $mailbox, $sender, $sender, '', $thread,
                        ['displayName' => $sender, 'emailAddress' => $sender]);
                    $conversation = $this->kernel->create('ExternalConversation', [
                        'name' => $email->getSubject() ?: $sender, 'subject' => $email->getSubject(),
                        'channelId' => $channel->getId(), 'externalId' => $thread, 'externalUserId' => $sender,
                        'identityId' => $identity->getId(), 'language' => 'en', 'status' => 'replied',
                        'controlMode' => 'human', 'needsManualMatch' => $identity->get('linkStatus') !== 'confirmed',
                        'unreadCount' => 0,
                    ]);
                }
                $external = $this->kernel->create('ExternalMessage', [
                    'name' => 'OUT ' . $externalId, 'conversationId' => $conversation->getId(),
                    'externalId' => $externalId, 'direction' => 'outbound', 'senderName' => $mailbox,
                    'senderExternalId' => $mailbox, 'sentAt' => $sentAt, 'body' => $body,
                    'deliveryStatus' => 'sent', 'contentHash' => hash('sha256', $externalId . '|outbound|' . $body),
                    'rawPayload' => $metadata,
                ]);
                if ((string) $conversation->get('lastMessageAt') <= $sentAt) {
                    $conversation->set('lastMessageAt', $sentAt);
                    $conversation->set('lastMessagePreview', mb_substr(preg_replace('/\s+/', ' ', $body), 0, 220));
                }
                if ((string) $conversation->get('lastOutboundAt') <= $sentAt) {
                    $conversation->set('lastOutboundAt', $sentAt);
                }
                if ((string) $conversation->get('lastInboundAt') <= $sentAt) {
                    $conversation->set('status', 'replied');
                }
                $this->kernel->save($conversation);
                $result = ['messageId' => $external->getId(), 'conversationId' => $conversation->getId(), 'deduplicated' => false];
            }
            $this->stamp($external, $email, $parser->getHeader($message, 'Date'));
            $this->sales->receive($external, $email, $salesHeaders);
            $results[] = ['sourceId' => $externalId, 'nativeEmailId' => $email->getId(), ...$result];
        }
        return ['mailbox' => $mailbox, 'results' => $results];
    }

    private function stamp(\Espo\ORM\Entity $message, Email $email, ?string $rawDate): void
    {
        $timestamp = $rawDate ? strtotime($rawDate) : false;
        $verified = $timestamp !== false && gmdate('Y-m-d H:i:s', $timestamp) === $email->getDateSent()?->toString();
        $message->set('sourceTimestampRaw', mb_substr((string) $rawDate, 0, 255));
        $message->set('timestampConfidence', $verified ? 'high' : 'low');
        $this->kernel->save($message);
    }

    private function channel(string $mailbox): \Espo\ORM\Entity
    {
        $channel = $this->em->getRDBRepository('ExternalChannel')
            ->where(['type' => 'Email', 'accountHandle' => $mailbox])->findOne();
        if ($channel) {
            if (!$channel->get('enabled')) {
                throw new RuntimeException('Email channel is disabled.');
            }
            return $channel;
        }
        return $this->kernel->create('ExternalChannel', [
            'name' => 'Zoho · ' . $mailbox, 'type' => 'Email', 'accountHandle' => $mailbox,
            'enabled' => true, 'connectionStatus' => 'healthy',
        ]);
    }
}
