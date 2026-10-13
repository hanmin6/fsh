<?php
namespace Espo\Custom\Classes\Jobs;
use Espo\Core\Job\Job;
use Espo\Core\Job\Job\Data;
use Espo\Custom\Tools\Fusanhe\SalesEnrichment;
final class SalesEnrich implements Job
{
    public function __construct(private SalesEnrichment $service) {}
    public function run(Data $data): void {$this->service->tick();}
}
