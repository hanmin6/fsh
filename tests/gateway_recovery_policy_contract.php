<?php
namespace Espo\Core\Exceptions { class BadRequest extends \RuntimeException {} }
namespace {
require $argv[1] . '/custom/Espo/Custom/Tools/Fusanhe/GatewayRecoveryPolicy.php';
use Espo\Custom\Tools\Fusanhe\GatewayRecoveryPolicy as Policy;
$base = ['worker'=>'mic','processRunning'=>true,'sessionState'=>'healthy','sourceAgeSeconds'=>10,'sourceBusy'=>false,'pending'=>false,'hasReplayPayload'=>false,'autoLoginSupported'=>true,'reasonCode'=>'healthy'];
function check(bool $condition, string $label): void { if (!$condition) throw new \RuntimeException($label); }
check(Policy::actions(Policy::observation($base)) === ['wait'], 'healthy must be idle');
$login = array_replace($base, ['sessionState'=>'login_required','reasonCode'=>'login_required']);
check(in_array('auto_login', Policy::actions($login), true), 'saved login recovery missing');
$captcha = array_replace($login, ['sessionState'=>'verification_required','reasonCode'=>'verification_required']);
check(!in_array('auto_login', Policy::actions($captcha), true), 'verification must not submit passwords');
$pending = array_replace($base, ['worker'=>'bridge','pending'=>true,'reasonCode'=>'pending_batch_conflict']);
check(!in_array('replay_pending', Policy::actions($pending), true), 'missing original body must not replay');
check(in_array('replay_pending', Policy::actions(array_replace($pending, ['hasReplayPayload'=>true])), true), 'retained body can replay');
$busy = array_replace($base, ['sourceAgeSeconds'=>2000,'sourceBusy'=>true,'reasonCode'=>'source_stale']);
check(!in_array('retry_sync', Policy::actions($busy), true), 'busy source must not be interrupted');
$stale = array_replace($base, ['reasonCode'=>'source_stale']);
check(in_array('retry_sync', Policy::actions($stale), true), 'explicit source failure must allow retry even with fresh bridge receipt');
$hung = array_replace($base, ['reasonCode'=>'worker_unresponsive']);
check(in_array('restart_worker', Policy::actions(Policy::observation($hung)), true), 'hung worker must allow scoped restart');
check(!in_array('restart_worker', Policy::actions(array_replace($hung, ['worker'=>'bridge'])), true), 'browser watchdog must not restart bridge');
try { Policy::observation($base + ['password'=>'fixture']); throw new \RuntimeException('sensitive input accepted'); }
catch (\Espo\Core\Exceptions\BadRequest) {}
echo "recovery policy contracts passed\n";
}
