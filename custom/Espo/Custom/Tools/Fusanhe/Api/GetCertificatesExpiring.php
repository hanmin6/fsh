<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;

/**
 * Read-only expiry list. Default horizon 60 days, max 365. Expired and
 * soon-expiring records are returned with a computed flag; nothing is written.
 */
final class GetCertificatesExpiring extends AbstractFusanheAction
{
    public function process(Request $request): Response
    {
        $this->requireFeature('certificates');
        $this->requireScope('FusanheCertificate', 'read');
        $days = (int) ($request->getQueryParam('days') ?? 60);
        $days = max(1, min(365, $days));
        $today = new \DateTimeImmutable('today');
        $horizon = $today->modify("+{$days} days")->format('Y-m-d');
        $todayStr = $today->format('Y-m-d');

        $list = [];
        $query = $this->em->getRDBRepository('FusanheCertificate')
            ->where(['status' => 'approved']);
        // Row-level visibility follows the user's read level on the scope.
        if (!$this->user->isAdmin()) {
            $level = $this->acl->getLevel('FusanheCertificate', 'read');
            if ($level === 'own') {
                $query->where(['assignedUserId' => $this->user->getId()]);
            } elseif ($level === 'team') {
                $teamIds = method_exists($this->user, 'getTeamIdList') ? $this->user->getTeamIdList() : [];
                $query->where([
                    'OR' => [
                        ['assignedUserId' => $this->user->getId()],
                        ['teamsIds' => $teamIds],
                    ],
                ]);
            }
        }
        $records = $query->find();
        foreach ($records as $cert) {
            $validTo = $cert->get('validTo');
            if (!$validTo || (string) $validTo > $horizon) {
                continue;
            }
            $list[] = [
                'id' => $cert->getId(),
                'name' => $cert->get('name'),
                'type' => $cert->get('type'),
                'scopeLevel' => $cert->get('scopeLevel'),
                'product' => $cert->get('productName'),
                'certificateNo' => $cert->get('certificateNo'),
                'validTo' => $validTo,
                'expired' => (string) $validTo < $todayStr,
            ];
        }
        usort($list, fn($a, $b) => strcmp((string) $a['validTo'], (string) $b['validTo']));
        return ResponseComposer::json(['days' => $days, 'total' => count($list), 'list' => $list]);
    }
}
