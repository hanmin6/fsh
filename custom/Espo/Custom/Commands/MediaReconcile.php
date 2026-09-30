<?php
namespace Espo\Custom\Commands;
use Espo\Core\Console\Command;
use Espo\Core\Console\Command\Params;
use Espo\Core\Console\IO;
use Espo\Custom\Tools\Fusanhe\CreativeService;
/** Read-only provider polling and result persistence; never creates a paid task. */
final class MediaReconcile implements Command
{
    public function __construct(private CreativeService $service) {}
    public function run(Params $params, IO $io): void
    {
        try { $io->writeLine('media_jobs_checked=' . $this->service->tick()); }
        catch (\Throwable) { $io->writeLine('media_reconciliation_failed'); $io->setExitStatus(1); }
    }
}
