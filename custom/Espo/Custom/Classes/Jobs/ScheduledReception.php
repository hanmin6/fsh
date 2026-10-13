<?php
namespace Espo\Custom\Classes\Jobs;
use Espo\Core\Job\Job;
use Espo\Core\Job\Job\Data;
use Espo\Custom\Tools\Fusanhe\ScheduledReceptionService;
final class ScheduledReception implements Job
{
    public function __construct(private ScheduledReceptionService $service) {}
    public function run(Data $data): void { $this->service->tick(); }
}
