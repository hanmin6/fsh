<?php
namespace Espo\Custom\Classes\Jobs;
use Espo\Core\Job\Job;
use Espo\Core\Job\Job\Data;
use Espo\Custom\Tools\Fusanhe\MorningReportService;
final class MorningReport implements Job
{
    public function __construct(private MorningReportService $service) {}
    public function run(Data $data): void { $this->service->tick(); }
}
