<?php
namespace Espo\Custom\Tools\Fusanhe;

use DateTimeImmutable;
use DateTimeZone;

/** Private server execution journal, independent of morning-report delivery claims. */
final class AcquisitionRunStore
{
    public function directory(): string
    {
        $dir = ReceptionSettings::directory() . '/acquisition-runs';
        if (!is_dir($dir) && !mkdir($dir, 0700) && !is_dir($dir)) throw new \RuntimeException('acquisition_storage_unavailable');
        ReceptionSettings::protect($dir, 0700); return $dir;
    }
    private function write(string $name, array $value): void
    {
        $dir = $this->directory(); $tmp = tempnam($dir, 'run-');
        if (!$tmp) throw new \RuntimeException('acquisition_storage_unavailable');
        try {
            ReceptionSettings::protect($tmp, 0600);
            if (file_put_contents($tmp, json_encode($value, JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR)) === false ||
                !rename($tmp, $dir . '/' . $name . '.json')) throw new \RuntimeException('acquisition_storage_unavailable');
        } finally { if (is_file($tmp)) unlink($tmp); }
    }
    public function settings(): array
    {
        $path = $this->directory() . '/settings.json';
        return (is_file($path) ? json_decode(file_get_contents($path), true, 128, JSON_THROW_ON_ERROR) : []) +
            ['enabled' => false, 'timezone' => 'Asia/Shanghai', 'runTime' => '22:00', 'firstDate' => null];
    }
    public function configure(string $firstDate): array
    {
        if (!MorningReportStore::validDate($firstDate)) throw new \InvalidArgumentException('invalid_acquisition_date');
        $old = $this->settings();
        $settings = ['enabled' => true, 'timezone' => 'Asia/Shanghai', 'runTime' => '22:00',
            'firstDate' => $old['firstDate'] ?: $firstDate, 'updatedAt' => gmdate('c')];
        $this->write('settings', $settings); return $settings;
    }
    public function read(string $date): ?array
    {
        if (!MorningReportStore::validDate($date)) throw new \InvalidArgumentException('invalid_acquisition_date');
        $path = $this->directory() . '/' . $date . '.json';
        return is_file($path) ? json_decode(file_get_contents($path), true, 128, JSON_THROW_ON_ERROR) : null;
    }
    public function save(array $run): void
    {
        if (!MorningReportStore::validDate($run['date'] ?? '') || ($run['trigger'] ?? '') !== 'scheduled' ||
            !in_array($run['status'] ?? '', ['running','completed','partial','failed','missed'], true)) throw new \InvalidArgumentException('invalid_acquisition_run');
        $this->write($run['date'], $run);
    }
    public static function summary(string $reportDate, array $settings, ?array $run, DateTimeImmutable $asOf, array $leads = []): array
    {
        $zone = new DateTimeZone('Asia/Shanghai');
        $date = (new DateTimeImmutable($reportDate, $zone))->modify('-1 day')->format('Y-m-d');
        $due = new DateTimeImmutable($date . ' 22:00:00', $zone);
        $base = ['available' => true, 'enabled' => (bool) ($settings['enabled'] ?? false), 'date' => $date, 'runTime' => '22:00', 'warnings' => []];
        if (!$base['enabled']) return $base + ['status' => 'disabled'];
        if (!$settings['firstDate'] || $date < $settings['firstDate']) return $base + ['status' => 'not_started', 'firstDate' => $settings['firstDate']];
        if ($asOf < $due) return $base + ['status' => 'scheduled'];
        if (!$run || ($run['date'] ?? '') !== $date || ($run['trigger'] ?? '') !== 'scheduled') {
            $base['warnings'][] = '昨晚 22:00 获客任务缺少运行记录，请检查服务器定时任务';
            return $base + ['status' => 'missing'];
        }
        $status = $run['status'];
        if ($status === 'running' && $asOf->getTimestamp() - $due->getTimestamp() > 2700) {
            $status = 'stalled'; $base['warnings'][] = '昨晚获客任务未正常结束，请检查服务器执行日志';
        }
        if ($status === 'missed') $base['warnings'][] = '昨晚 22:00 获客任务错过执行窗口';
        $labels = ['xpoz_query_failed' => '社交平台搜索失败', 'xpoz_enrich_failed' => '部分公开资料补查失败',
            'social_timeout' => '社交搜索超时', 'social_failed' => '社交搜索未完成', 'qualify_timeout' => 'AI 筛选超时',
            'qualify_failed' => 'AI 筛选失败', 'evidence_invalid' => '部分 AI 原文证据未通过校验',
            'b2b_timeout' => '企业联系人搜索超时', 'b2b_failed' => '企业联系人搜索失败', 'b2b_record_invalid' => '部分联系人来源校验失败',
            'crm_import_failed' => '部分客资入库失败', 'crm_import_uncertain' => '部分客资入库结果待核对',
            'crm_bridge_failed' => '运行记录同步失败', 'rating_job_inactive' => '客户评级定时任务未开启',
            'pipeline_interrupted' => '服务器执行中断', 'pipeline_failed' => '获客流程执行失败'];
        $errors = [];
        foreach ($run['errors'] ?? [] as $code) $errors[$labels[$code] ?? '获客流程异常，需检查执行日志'] = true;
        if ($errors) $base['warnings'][] = '昨晚获客异常：' . implode('、', array_keys($errors));
        if (in_array($status, ['partial','failed'], true) && !$errors) $base['warnings'][] = '昨晚获客流程未全部完成，请检查执行日志';
        $routes = array_fill_keys(['human','ai','pending_rating','blocked'], 0); $seen = [];
        foreach ($leads as $lead) {
            $id = $lead['id'] ?? '';
            if (!$id || isset($seen[$id]) || !in_array($id, $run['createdLeadIds'] ?? [], true)) continue;
            $seen[$id] = true; $routes[AcquisitionRouting::route($lead)]++;
        }
        return $base + ['status' => $status, 'stats' => $run['stats'] ?? [], 'routes' => $routes,
            'startedAt' => $run['startedAt'] ?? null, 'finishedAt' => $run['finishedAt'] ?? null];
    }
    public static function text(array $run): string
    {
        if (empty($run['available'])) return "定时获客：运行记录读取失败，请检查 CRM。\n";
        if (empty($run['enabled'])) return '';
        $status = $run['status'] ?? '';
        if ($status === 'not_started') return "定时获客：从 {$run['firstDate']} 起，每天北京时间 22:00 执行。\n";
        if ($status === 'scheduled') return "定时获客：当天 22:00 的任务尚未到执行时间。\n";
        $labels = ['completed' => '已完成', 'partial' => '部分完成', 'failed' => '失败', 'running' => '执行中',
            'stalled' => '未正常结束', 'missing' => '缺少运行记录', 'missed' => '错过执行窗口'];
        $text = '定时获客：昨晚 22:00 ' . ($labels[$status] ?? '状态待核对') . '。';
        if (isset($run['stats'])) {
            $s = $run['stats'];
            $text .= '取得候选 ' . ($s['candidates'] ?? 0) . ' 条，筛选通过 ' . ($s['qualified'] ?? 0) .
                ' 条；新增入库 ' . ($s['created'] ?? 0) . ' 条，重复跳过 ' . ($s['deduplicated'] ?? 0) . ' 条。';
        }
        return $text . "\n";
    }
}
