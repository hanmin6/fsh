<?php
namespace Espo\Custom\Commands;
use Espo\Core\Console\Command;
use Espo\Core\Console\Command\Params;
use Espo\Core\Console\IO;
use Espo\Custom\Tools\Fusanhe\HistoryReconciliation;
use Espo\Custom\Tools\Fusanhe\ServiceKernel;
final class HistoryReconcile implements Command
{
    public function __construct(private ServiceKernel $kernel) {}
    public function run(Params $params, IO $io): void
    {
        $file = $params->getOption('file') ?? 'data/history-manifest.json';
        try {
            if (!is_file($file) || filesize($file) > 20000000) throw new \RuntimeException();
            $manifest = json_decode(file_get_contents($file), true, 512, JSON_THROW_ON_ERROR);
            $account = $manifest['accountHandle'] ?? null;
            if (!is_string($account) || !$account) throw new \RuntimeException();
            $channel = $this->kernel->repo('ExternalChannel')->where(['type' => 'Alibaba', 'accountHandle' => $account])->findOne();
            if (!$channel) throw new \RuntimeException();
            $actual = [];
            foreach ($this->kernel->repo('ExternalConversation')->where(['channelId' => $channel->getId()])->find() as $c) {
                $ids = [];
                foreach ($this->kernel->repo('ExternalMessage')->where(['conversationId' => $c->getId()])->find() as $m) $ids[] = (string) $m->get('externalId');
                $actual[(string) $c->get('externalId')] = $ids;
            }
            $result = HistoryReconciliation::compare($manifest, $actual);
            $result['checkedAt'] = $this->kernel->now();
            $result['manifestHash'] = hash_file('sha256', $file);
            $result['importedAtCheck'] = count($actual);
            $channel->set('historyCoverage', $result);
            $this->kernel->save($channel, ['fusanheInsights' => true]);
            $this->kernel->audit('history.reconcile', 'system', 'history-operator', 'ExternalChannel', $channel->getId(), $result['reconciled'] ? 'success' : 'partial', $result);
            $io->writeLine(json_encode($result, JSON_UNESCAPED_UNICODE));
            if (!$result['reconciled']) $io->setExitStatus(1);
        } catch (\Throwable $e) { $io->writeLine('invalid_manifest_or_channel'); $io->setExitStatus(1); }
    }
}
