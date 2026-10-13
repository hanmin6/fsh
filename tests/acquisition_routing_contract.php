<?php
namespace Espo\Core\Exceptions { class Conflict extends \RuntimeException {} }
namespace Espo\Core\Hook\Hook {
    interface BeforeSave { public function beforeSave(\Espo\ORM\Entity $entity, \Espo\ORM\Repository\Option\SaveOptions $options): void; }
    interface AfterSave { public function afterSave(\Espo\ORM\Entity $entity, \Espo\ORM\Repository\Option\SaveOptions $options): void; }
}
namespace Espo\ORM\Repository\Option {
    class SaveOptions { public function __construct(private array $values = []) {} public function get(string $name): mixed { return $this->values[$name] ?? null; } }
}
namespace Espo\ORM {
    class Entity {
        public function __construct(private string $type, private array $values, private array $fetched = [], private bool $new = false) {}
        public function get(string $name): mixed { return $this->values[$name] ?? null; }
        public function set(array|string $name, mixed $value = null): void { $this->values = array_merge($this->values, is_array($name) ? $name : [$name => $value]); }
        public function getFetched(string $name): mixed { return $this->fetched[$name] ?? null; }
        public function isAttributeChanged(string $name): bool { return $this->get($name) !== $this->getFetched($name); }
        public function isNew(): bool { return $this->new; }
        public function getId(): string { return $this->get('id'); }
        public function getEntityType(): string { return $this->type; }
    }
    class TestRepository {
        private array $where = [];
        public function __construct(private array $rows) {}
        public function where(array $where): self { $this->where = $where; return $this; }
        public function find(): array { return array_values(array_filter($this->rows, fn($row) => !array_filter($this->where, fn($v, $k) => $row->get($k) !== $v, ARRAY_FILTER_USE_BOTH))); }
        public function findOne(): ?Entity { return $this->find()[0] ?? null; }
    }
    class EntityManager {
        public array $rows = [], $saves = [];
        public function getEntityById(string $type, string $id): ?Entity { return $this->rows[$type][$id] ?? null; }
        public function getRDBRepository(string $type): TestRepository { return new TestRepository($this->rows[$type] ?? []); }
        public function saveEntity(Entity $entity, array $options = []): void { $this->saves[] = [$entity, $options]; $this->rows[$entity->getEntityType()][$entity->getId()] = $entity; }
    }
}
namespace {
$root = $argv[1] ?? getcwd();
require $root . '/custom/Espo/Custom/Tools/Fusanhe/AcquisitionRouting.php';
require $root . '/custom/Espo/Custom/Tools/Fusanhe/AcquisitionRoutingService.php';
require $root . '/custom/Espo/Custom/Hooks/Lead/RouteAcquisition.php';
require $root . '/custom/Espo/Custom/Hooks/ExternalConversation/RouteAcquisition.php';
require $root . '/custom/Espo/Custom/Hooks/OutboundTask/AcquisitionRoutingGuard.php';
use Espo\Custom\Tools\Fusanhe\AcquisitionRouting as Policy;
use Espo\Custom\Tools\Fusanhe\AcquisitionRoutingService;
use Espo\ORM\Entity;
use Espo\ORM\EntityManager;
use Espo\ORM\Repository\Option\SaveOptions;
function checkRoute(bool $value, string $message): void { if (!$value) throw new \RuntimeException($message); }
function blockedRoute(callable $operation, string $message): void { try { $operation(); } catch (\Espo\Core\Exceptions\Conflict) { return; } throw new \RuntimeException($message); }
foreach (['S' => 'human', 'A' => 'human', 'B' => 'ai', 'C' => 'ai', 'D' => 'ai', '' => 'pending_rating', 'invented' => 'pending_rating'] as $rating => $route) {
    checkRoute(Policy::route(['rating' => $rating]) === $route, 'incorrect route for ' . $rating);
}
checkRoute(Policy::route(['rating' => 'C', 'ratingSource' => 'manual', 'aiRating' => 'A', 'aiRatingStatus' => 'completed']) === 'ai', 'AI must not overwrite manual rating');
checkRoute(Policy::route(['rating' => '', 'ratingSource' => 'manual', 'aiRating' => 'A', 'aiRatingStatus' => 'completed']) === 'pending_rating', 'manual clear must not restore AI rating');
checkRoute(Policy::route(['aiRating' => 'B', 'aiRatingStatus' => 'completed']) === 'ai', 'completed automatic rating fallback');
checkRoute(Policy::route(['aiRating' => 'B', 'aiRatingStatus' => 'running']) === 'pending_rating', 'unfinished AI rating cannot route');
foreach (['optedOut', 'restricted'] as $policy) checkRoute(Policy::route(['rating' => 'B', 'fusanheContactPolicy' => $policy]) === 'blocked', 'contact policy wins');
checkRoute(Policy::route(['rating' => 'B', 'fusanheDoNotContact' => true]) === 'blocked', 'do-not-contact wins');
checkRoute(Policy::isAcquisition(['fusanheSourceSystem' => 'Muse', 'fusanheSourceId' => 'xpoz:1']), 'Muse acquisition recognised');
checkRoute(!Policy::isAcquisition(['fusanheSourceSystem' => 'Website']), 'ordinary inbound lead excluded');

$em = new EntityManager();
$service = new AcquisitionRoutingService($em);
$values = ['id' => 'l1', 'fusanheSourceSystem' => 'Muse', 'fusanheSourceId' => 'xpoz:1', 'rating' => 'B'];
$lead = new Entity('Lead', $values, $values);
$em->rows['Lead']['l1'] = $lead;
$leadHook = new \Espo\Custom\Hooks\Lead\RouteAcquisition($service);
$leadHook->beforeSave($lead, new SaveOptions());
checkRoute($lead->get('fusanheFollowUpRoute') === 'ai' && $lead->get('fusanheFollowUpRoutedAt'), 'route persisted with timestamp');
$time = $lead->get('fusanheFollowUpRoutedAt');
$lead->set('fusanheFollowUpRoute', 'human');
$leadHook->beforeSave($lead, new SaveOptions());
checkRoute($lead->get('fusanheFollowUpRoute') === 'ai', 'clients cannot forge route');
$leadHook->beforeSave($lead, new SaveOptions());
checkRoute($lead->get('fusanheFollowUpRoutedAt') === $time, 'unchanged route does not churn timestamp');

$conversation = new Entity('ExternalConversation', ['id' => 'c1', 'leadId' => 'l1', 'controlMode' => 'aiAssist'], ['id' => 'c1', 'leadId' => 'l1', 'controlMode' => 'aiAssist']);
$em->rows['ExternalConversation']['c1'] = $conversation;
$conversationHook = new \Espo\Custom\Hooks\ExternalConversation\RouteAcquisition($service);
$conversationHook->beforeSave($conversation, new SaveOptions());
checkRoute($conversation->get('controlMode') === 'aiAssist' && $service->taskCanRun($conversation), 'medium value allows existing AI workflow');
$lead->set('rating', 'A');
$leadHook->beforeSave($lead, new SaveOptions());
$leadHook->afterSave($lead, new SaveOptions());
checkRoute($conversation->get('controlMode') === 'human', 'high value immediately promotes existing conversation to human');
$lead->set('rating', 'C');
$leadHook->beforeSave($lead, new SaveOptions());
$leadHook->afterSave($lead, new SaveOptions());
$conversationHook->beforeSave($conversation, new SaveOptions());
checkRoute($conversation->get('controlMode') === 'human' && !$service->taskCanRun($conversation), 'downgrade preserves human takeover');

$conversation->set('controlMode', 'aiAssist');
$lead->set('rating', 'B');
$task = new Entity('OutboundTask', ['id' => 't1', 'conversationId' => 'c1', 'status' => 'claimed'], ['id' => 't1', 'conversationId' => 'c1', 'status' => 'pending']);
$taskHook = new \Espo\Custom\Hooks\OutboundTask\AcquisitionRoutingGuard($service, $em);
$taskHook->beforeSave($task, new SaveOptions(['fusanheService' => true]));
checkRoute($service->taskCanRun($conversation), 'eligible medium task allowed');
$lead->set('rating', 'A');
blockedRoute(fn() => $taskHook->beforeSave($task, new SaveOptions(['fusanheService' => true])), 'stale pending task may not claim after high-value upgrade');
$task->set('status', 'sending');
blockedRoute(fn() => $taskHook->beforeSave($task, new SaveOptions(['fusanheService' => true])), 'rating rechecked before channel handoff');
$lead->set('rating', '');
blockedRoute(fn() => $taskHook->beforeSave($task, new SaveOptions(['fusanheService' => true])), 'unrated acquisition may not send');
$lead->set(['rating' => 'C', 'fusanheContactPolicy' => 'optedOut']);
blockedRoute(fn() => $taskHook->beforeSave($task, new SaveOptions(['fusanheService' => true])), 'opt-out acquisition may not send');
$task->set('status', 'sent');
$taskHook->beforeSave($task, new SaveOptions(['fusanheService' => true]));
checkRoute(true, 'already handed off delivery results must remain recordable');

$lead->set(['rating' => 'A', 'fusanheContactPolicy' => 'unknown']);
$resume = new Entity('ExternalConversation', ['id' => 'c1', 'leadId' => 'l1', 'controlMode' => 'aiAssist'], ['id' => 'c1', 'leadId' => 'l1', 'controlMode' => 'human']);
blockedRoute(fn() => $conversationHook->beforeSave($resume, new SaveOptions(['fusanheService' => true])), 'high value cannot resume automatic control');
$legacyLead = new Entity('Lead', ['id' => 'legacy', 'rating' => 'A', 'fusanheSourceSystem' => 'Website']);
$em->rows['Lead']['legacy'] = $legacyLead;
$legacyConversation = new Entity('ExternalConversation', ['id' => 'legacy-c', 'leadId' => 'legacy', 'controlMode' => 'aiAssist']);
$conversationHook->beforeSave($legacyConversation, new SaveOptions());
checkRoute($legacyConversation->get('controlMode') === 'aiAssist' && $service->taskCanRun($legacyConversation), 'legacy inbound workflow unchanged');
$lead->set(['rating' => 'B', 'fusanheContactPolicy' => 'unknown']);
checkRoute($service->persist($lead) === 'ai' && $lead->get('fusanheFollowUpRoute') === 'ai', 'backfill persists current routing');
checkRoute($em->saves[count($em->saves) - 1][1]['fusanheService'] === true, 'backfill uses service-owned write boundary');
echo "PASS: acquisition value routing, manual priority, persisted routes, human takeover, fresh send guards and legacy isolation\n";
}
