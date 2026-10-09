<?php
namespace Espo\Custom\Classes\Jobs;

use Espo\Core\Job\Job;
use Espo\Core\Job\Job\Data;
use Espo\Custom\Tools\Fusanhe\OutreachEvidenceService;

/** Retries explicitly queued research; it never sends external messages. */
final class OutreachResearch implements Job
{
    public function __construct(private OutreachEvidenceService $service) {}

    public function run(Data $data): void
    {
        $this->service->tick();
    }
}
