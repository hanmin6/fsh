<?php
namespace Espo\Custom\Tools\Fusanhe;

use Espo\Core\Acl;
use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Exceptions\NotFound;
use Espo\Entities\User;
use Espo\ORM\Entity;
use Espo\ORM\EntityManager;

final class BossInsightsService
{
    public function __construct(private EntityManager $em, private Acl $acl, private User $user) {}

    private function base(): array
    {
        if (!$this->user->isAdmin() && !$this->acl->checkScope('ExternalConversation', 'read')) throw new Forbidden();
        $channels = [];
        foreach ($this->em->getRDBRepository('ExternalChannel')->where(['type' => 'Alibaba'])->find() as $c) $channels[] = $c->getId();
        $where = ['channelId' => $channels ?: ['__none__'], 'lastSourceSyncAt!=' => null];
        // A conservative own-only subset for team/own ACL; never leak org totals.
        if (!$this->user->isAdmin() && $this->acl->getLevel('ExternalConversation', 'read') !== 'all') $where['assignedUserId'] = $this->user->getId();
        return $where;
    }

    private function repo() { return $this->em->getRDBRepository('ExternalConversation'); }

    public function overview(string $query = '', string $status = '', int $offset = 0, int $limit = 25): array
    {
        $base = $this->base();
        $where = $base;
        $query = mb_substr(trim($query), 0, 100);
        if ($query !== '') $where['OR'] = [['name*' => '%' . $query . '%'], ['externalId*' => '%' . $query . '%'], ['externalUserId*' => '%' . $query . '%']];
        if (in_array($status, ['completed', 'failed', 'stale'], true)) $where['insightsStatus'] = $status;
        if ($status === 'pending') $where['AND'] = [['OR' => [['insightsStatus' => null], ['insightsStatus' => 'pending']]]];
        if ($status === 'unmatched') $where['needsManualMatch'] = true;
        $offset = max(0, $offset); $limit = max(1, min(100, $limit));
        $list = [];
        foreach ($this->repo()->where($where)->order('lastMessageAt', 'DESC')->order('id', 'ASC')->limit($offset, $limit)->find() as $c) $list[] = $this->row($c);
        $count = fn(array $extra = []) => $this->repo()->where(array_merge($base, $extra))->count();
        $latest = $this->repo()->where($base)->order('lastSourceSyncAt', 'DESC')->findOne();
        $analyzed = $this->repo()->where(array_merge($base, ['insightsAt!=' => null]))->order('insightsAt', 'DESC')->findOne();
        $suggestions = []; $suggestionTotal = 0;
        // Stream the whole authorized set in bounded chunks; never silently rank only one page.
        for ($at = 0; ; $at += 200) {
            $rows = $this->repo()->where(array_merge($base, ['status!=' => 'closed']))->order('id')->limit($at, 200)->find();
            foreach ($rows as $c) {
                $s = HistorySignals::suggestion($c->getValueMap() ? (array) $c->getValueMap() : []);
                if ($s) { $suggestionTotal++; $suggestions[] = $s + $this->row($c); }
            }
            usort($suggestions, fn($a, $b) => [$a['priority'], $a['lastMessageAt'] ?? '', $a['id']] <=> [$b['priority'], $b['lastMessageAt'] ?? '', $b['id']]);
            $suggestions = array_slice($suggestions, 0, 50);
            if (count($rows) < 200) break;
        }
        usort($suggestions, fn($a, $b) => [$a['priority'], $a['lastMessageAt'] ?? '', $a['id']] <=> [$b['priority'], $b['lastMessageAt'] ?? '', $b['id']]);
        $coverageReport = $this->coverageReport($base);
        return [
            'date' => HistorySignals::day(), 'timezone' => 'Asia/Shanghai', 'outboundPaused' => ControlService::outboundPaused(),
            'scope' => isset($base['assignedUserId']) ? 'own' : 'all',
            'coverage' => array_merge(['platformVisible' => null, 'imported' => $count(), 'failedSync' => null,
                'recordedSyncErrors' => $count(['syncError!=' => null]),
                'pendingIdentity' => $count(['needsManualMatch' => true]),
                'analysisCompleted' => $count(['insightsStatus' => 'completed']), 'analysisFailed' => $count(['insightsStatus' => 'failed']),
                'analysisStale' => $count(['insightsStatus' => 'stale']),
                'lastSyncAt' => $latest?->get('lastSourceSyncAt'), 'lastAnalysisAt' => $analyzed?->get('insightsAt'),
                'reconciled' => false, 'reason' => '待采集端提供完整分页及消息对账；平台可见总数和未入库失败数未知。仅统计带同步来源的 Alibaba 会话。'], $coverageReport),
            'list' => $list, 'total' => $this->repo()->where($where)->count(), 'offset' => $offset, 'limit' => $limit,
            'suggestions' => array_slice($suggestions, 0, 50), 'suggestionTotal' => $suggestionTotal,
        ];
    }

    private function coverageReport(array $base): array
    {
        if (isset($base['assignedUserId'])) return [];
        $ids = $base['channelId'];
        $reports = [];
        foreach ($ids as $id) {
            $channel = $this->em->getEntityById('ExternalChannel', $id);
            if (!$channel) continue;
            $count = $this->repo()->where(['channelId' => $id, 'lastSourceSyncAt!=' => null])->count();
            $report = (array) ($channel->get('historyCoverage') ?? []);
            // Mock-only channels are not part of the historical account set.
            if (!$count && !$report) continue;
            if (!$report) return [];
            $newer = $this->repo()->where(['channelId' => $id, 'lastSourceSyncAt>' => $report['checkedAt']])->count();
            if ($newer || $count !== ($report['importedAtCheck'] ?? -1)) {
                $report['reconciled'] = false;
                $report['reason'] = '对账后数据发生变化，需要重新核对。';
            }
            $reports[] = $report;
        }
        if (!$reports) return [];
        $complete = !in_array(false, array_column($reports, 'reconciled'), true);
        $known = !in_array(null, array_column($reports, 'platformVisible'), true);
        return ['platformVisible' => $known ? array_sum(array_column($reports, 'platformVisible')) : null,
            'failedSync' => array_sum(array_column($reports, 'failedSync')), 'reconciled' => $complete,
            'reason' => $complete ? '已全部导入：会话与消息稳定 ID 逐项对账相符，失败为零。' : implode(' ', array_unique(array_column($reports, 'reason')))];
    }

    private function row(Entity $c): array
    {
        $customer = null;
        foreach (['Account' => 'accountId', 'Contact' => 'contactId', 'Lead' => 'leadId'] as $type => $field) {
            $id = $c->get($field);
            $e = $id ? $this->em->getEntityById($type, $id) : null;
            if ($e && ($this->user->isAdmin() || $this->acl->checkEntity($e, 'read'))) { $customer = ['type' => $type, 'id' => $id]; break; }
        }
        return ['id' => $c->getId(), 'name' => $c->get('name'), 'externalId' => $c->get('externalId'),
            'owner' => $c->get('assignedUserName') ?: '未分配', 'lastMessageAt' => $c->get('lastMessageAt'),
            'needsManualMatch' => (bool) $c->get('needsManualMatch'), 'customer' => $customer,
            'analysisStatus' => $c->get('insightsStatus') ?: 'pending', 'analysisAt' => $c->get('insightsAt'),
            'analysisError' => $c->get('insightsError')];
    }

    public function detail(string $id): array
    {
        $c = $this->repo()->where(array_merge($this->base(), ['id' => $id]))->findOne();
        if (!$c) throw new NotFound();
        if (!$this->user->isAdmin() && !$this->acl->checkEntity($c, 'read')) throw new Forbidden();
        $analysis = $c->get('insightsData');
        if (is_object($analysis)) $analysis = (array) $analysis;
        $analysis = is_array($analysis) ? $analysis : null;
        $evidence = [];
        foreach (($analysis['evidenceMessageIds'] ?? []) as $messageId) {
            $m = $this->em->getEntityById('ExternalMessage', $messageId);
            if (!$m || $m->get('conversationId') !== $id || (!$this->user->isAdmin() && !$this->acl->checkEntity($m, 'read'))) {
                // A summary must not become a side channel around message ACL.
                $analysis = null; $evidence = []; break;
            }
            $evidence[] = ['id' => $m->getId(), 'sentAt' => $m->get('sentAt'), 'direction' => $m->get('direction')];
        }
        return $this->row($c) + ['analysis' => $analysis, 'evidence' => $evidence,
            'model' => $c->get('insightsModel'), 'promptVersion' => HistorySignals::VERSION,
            'analysisNotice' => $analysis ? '匿名信号分析，业务事实请核对原文。' : '尚无可读取的分析；未完成、失败或证据无权限。'];
    }
}
