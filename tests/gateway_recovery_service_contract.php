<?php
namespace Espo\Core\Exceptions { class BadRequest extends \RuntimeException {} class Forbidden extends \RuntimeException {} }
namespace Espo\ORM {
    class Entity { public function __construct(private array $data) {} public function get($key) { return $this->data[$key] ?? null; } public function getId() { return 'fixture-agent'; } }
    class EntityManager {}
}
namespace Espo\Custom\Tools\Fusanhe {
    class ServiceKernel { public array $events = []; public function audit(...$args): void { $this->events[] = $args; } }
    class TextGateway { public string $action='wait'; public int $calls=0; public function complete(...$args): array { $this->calls++; return ['content'=>json_encode(['action'=>$this->action,'reasonZh'=>'fixture']), 'model'=>'gpt-6.1-sol']; } }
}
namespace {
require $argv[1] . '/custom/Espo/Custom/Tools/Fusanhe/GatewayRecoveryPolicy.php';
require $argv[1] . '/custom/Espo/Custom/Tools/Fusanhe/GatewayRecoveryService.php';
$text = new \Espo\Custom\Tools\Fusanhe\TextGateway();
$kernel = new \Espo\Custom\Tools\Fusanhe\ServiceKernel();
$service = new \Espo\Custom\Tools\Fusanhe\GatewayRecoveryService(new \Espo\ORM\EntityManager(), $kernel, $text);
$agent = new \Espo\ORM\Entity(['capabilities'=>['GatewayRecovery:MadeInChina:fixture']]);
$base = ['worker'=>'mic','processRunning'=>true,'sessionState'=>'healthy','sourceAgeSeconds'=>10,'sourceBusy'=>false,'pending'=>false,'hasReplayPayload'=>false,'autoLoginSupported'=>true,'reasonCode'=>'healthy'];
$input = (object) ['operation'=>'plan','channelType'=>'MadeInChina','accountHandle'=>'fixture','observation'=>(object)$base];
if ($service->execute($input,$agent)['action'] !== 'wait') throw new \RuntimeException('healthy plan failed');
$bad = clone $input; $bad->accountHandle='foreign';
try { $service->execute($bad,$agent); throw new \RuntimeException('foreign recovery scope accepted'); } catch (\Espo\Core\Exceptions\Forbidden) {}
if ($text->calls !== 1) throw new \RuntimeException('out-of-scope request reached model');
$bad = clone $input; $bad->observation=(object)($base+['password'=>'fixture-secret']);
try { $service->execute($bad,$agent); throw new \RuntimeException('sensitive observation accepted'); } catch (\Espo\Core\Exceptions\BadRequest) {}
if ($text->calls !== 1) throw new \RuntimeException('password reached model');
$text->action='delete_database';
try { $service->execute($input,$agent); throw new \RuntimeException('unapproved action accepted'); } catch (\RuntimeException $error) { if ($error->getMessage() !== 'recovery_invalid_model_action') throw $error; }
$service->execute((object)['operation'=>'report','channelType'=>'MadeInChina','accountHandle'=>'fixture','action'=>'needs_human','resultCode'=>'login_not_confirmed'],$agent);
if (end($kernel->events)[5] !== 'failure') throw new \RuntimeException('blocked recovery reported as success');
$service->execute((object)['operation'=>'report','channelType'=>'MadeInChina','accountHandle'=>'fixture','action'=>'wait','resultCode'=>'healthy_verified'],$agent);
if (end($kernel->events)[5] !== 'success') throw new \RuntimeException('verified recovery reported as failure');
echo "recovery service scope and model-action contracts passed\n";
}
