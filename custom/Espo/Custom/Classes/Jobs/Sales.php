<?php
namespace Espo\Custom\Classes\Jobs;
use Espo\Core\Job\Job;
use Espo\Core\Job\Job\Data;
use Espo\Custom\Tools\Fusanhe\SalesService;
final class Sales implements Job
{
    public function __construct(private SalesService $service) {}
    public function run(Data $data): void {$this->service->tick();}
}
