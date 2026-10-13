<?php
namespace Espo\Custom\Tools\Fusanhe;

use Espo\Core\Exceptions\BadRequest;

/** Operational signals only: never browser HTML, passwords or customer message bodies. */
final class GatewayRecoveryPolicy
{
    public static function observation(array $input): array
    {
        $keys = ['worker', 'processRunning', 'sessionState', 'sourceAgeSeconds', 'sourceBusy',
            'pending', 'hasReplayPayload', 'autoLoginSupported', 'reasonCode'];
        if (array_diff(array_keys($input), $keys)) throw new BadRequest('Unexpected recovery observation field.');
        if (!in_array($input['worker'] ?? '', ['mic', 'bridge', 'alibaba'], true)) throw new BadRequest('Unknown recovery worker.');
        foreach (['processRunning', 'sourceBusy', 'pending', 'hasReplayPayload', 'autoLoginSupported'] as $key) {
            if (!is_bool($input[$key] ?? null)) throw new BadRequest('Recovery flags must be boolean.');
        }
        if (!is_int($input['sourceAgeSeconds'] ?? null) || $input['sourceAgeSeconds'] < 0 || $input['sourceAgeSeconds'] > 31536000) throw new BadRequest('Invalid source age.');
        if (!in_array($input['sessionState'] ?? '', ['healthy', 'login_required', 'verification_required', 'unavailable'], true)) throw new BadRequest('Unknown session state.');
        if (!in_array($input['reasonCode'] ?? '', ['healthy', 'process_stopped', 'worker_unresponsive', 'login_required', 'verification_required', 'pending_batch_conflict', 'sync_failed', 'source_stale', 'browser_unavailable', 'incomplete_history', 'gateway_or_sync_unavailable'], true)) throw new BadRequest('Unknown recovery reason.');
        return $input;
    }

    public static function actions(array $o): array
    {
        $actions = ['wait', 'needs_human'];
        if (!$o['processRunning']) return [...$actions, 'restart_worker'];
        if ($o['sessionState'] === 'healthy' && !$o['pending'] && $o['sourceAgeSeconds'] <= 1800 && $o['reasonCode'] === 'healthy') return ['wait'];
        if ($o['sessionState'] === 'verification_required') return $actions;
        if ($o['pending']) return $o['hasReplayPayload'] && $o['worker'] === 'bridge' ? [...$actions, 'replay_pending'] : $actions;
        if ($o['sessionState'] === 'login_required') return $o['autoLoginSupported'] && $o['worker'] !== 'bridge' ? [...$actions, 'auto_login'] : $actions;
        if (!$o['sourceBusy'] && $o['worker'] !== 'bridge'
            && ($o['sourceAgeSeconds'] > 1800 || $o['reasonCode'] === 'source_stale')) $actions[] = 'retry_sync';
        if ($o['reasonCode'] === 'worker_unresponsive' && !$o['sourceBusy'] && $o['worker'] !== 'bridge') $actions[] = 'restart_worker';
        if ($o['sessionState'] === 'unavailable' && !$o['sourceBusy'] && $o['worker'] !== 'bridge') $actions[] = 'restart_worker';
        return $actions;
    }
}
