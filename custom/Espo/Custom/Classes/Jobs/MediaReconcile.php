<?php
namespace Espo\Custom\Classes\Jobs;
use Espo\Core\Job\Job;
use Espo\Core\Job\Job\Data;
use Espo\Custom\Tools\Fusanhe\CreativeService;
/** Poll and archive results independently of the creative browser page. */
final class MediaReconcile implements Job
{
    public function __construct(private CreativeService $service) {}
    public function run(Data $data): void { $this->service->tick(); }
}
