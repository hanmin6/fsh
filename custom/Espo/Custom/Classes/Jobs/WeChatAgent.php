<?php
namespace Espo\Custom\Classes\Jobs;
use Espo\Core\Job\Job;
use Espo\Core\Job\Job\Data;
use Espo\Custom\Tools\Fusanhe\WeChatAgentService;
final class WeChatAgent implements Job
{
    public function __construct(private WeChatAgentService $service) {}
    public function run(Data $data): void {$this->service->tick();}
}
