<?php
namespace Espo\Custom\Commands;
use Espo\Core\Console\Command;
use Espo\Core\Console\Command\Params;
use Espo\Core\Console\IO;
use Espo\Custom\Tools\Fusanhe\HistoryAnalysisWorker;
use Espo\Custom\Tools\Fusanhe\HistorySignals;

final class HistoryAnalyze implements Command
{
    public function __construct(private HistoryAnalysisWorker $worker) {}
    public function run(Params $params, IO $io): void
    {
        // Server operator only: no HTTP endpoint and no web-triggered paid work.
        $lock = fopen('data/history-analysis.lock', 'c+');
        if (!$lock || !flock($lock, LOCK_EX | LOCK_NB)) { $io->writeLine('analysis_worker_busy'); $io->setExitStatus(1); return; }
        try {
            if (!getenv('AI_API_KEY') || !getenv('AI_MODEL')) { $io->writeLine('ai_not_configured'); $io->setExitStatus(1); return; }
            $day = HistorySignals::day();
            $ledger = 'data/history-analysis-budget.json';
            $state = is_file($ledger) ? json_decode(file_get_contents($ledger), true) : null;
            if (!is_array($state) || ($state['day'] ?? null) !== $day) $state = ['day' => $day, 'reservedCalls' => 0];
            $max = max(1, min(100, (int) ($params->getOption('limit') ?? 5)));
            $reserve = function () use (&$state, $ledger): bool {
                if ($state['reservedCalls'] >= 100) return false;
                $state['reservedCalls']++;
                // Reserve before the request: interrupted requests still consume the budget.
                if (file_put_contents($ledger, json_encode($state), LOCK_EX) === false) throw new \RuntimeException('budget_write_failed');
                chmod($ledger, 0600);
                return true;
            };
            $stats = $this->worker->run($max, $params->hasFlag('retry'), fn($s) => $io->writeLine(json_encode($s)), $reserve);
            $io->writeLine(json_encode($stats + ['day' => $day, 'reservedCallsToday' => $state['reservedCalls'], 'dailyCallLimit' => 100, 'maxOutputTokensPerCall' => 900]));
            if ($stats['failed']) $io->setExitStatus(1);
        } finally { flock($lock, LOCK_UN); fclose($lock); }
    }
}
