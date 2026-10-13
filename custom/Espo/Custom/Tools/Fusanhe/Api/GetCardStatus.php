<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use DateTimeImmutable;
use DateTimeZone;
use Espo\Core\Acl;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Select\SelectBuilderFactory;
use Espo\Custom\Tools\Fusanhe\CardProgress;
use Espo\Custom\Tools\Fusanhe\ControlService;
use Espo\Entities\User;
use Espo\ORM\EntityManager;

final class GetCardStatus extends AbstractFusanheAction
{
    public function __construct(User $user, Acl $acl, EntityManager $em,
        private SelectBuilderFactory $selectBuilderFactory)
    { parent::__construct($user, $acl, $em); }

    public function process(Request $request): Response
    {
        $this->requireScope('Lead', 'read');
        $now = new DateTimeImmutable('now', new DateTimeZone('UTC'));
        $leads = (function () {
            for ($offset = 0; ; $offset += 200) {
                $query = $this->selectBuilderFactory->create()->from('Lead')
                    ->withStrictAccessControl()->buildQueryBuilder()
                    ->where(['fusanheSourceSystem' => ['Muse', 'Xpoz', 'OpenOutreach']])
                    ->select(['id', 'createdAt', 'fusanheSourceSystem', 'fusanheSourceId', 'rating',
                        'ratingSource', 'aiRating', 'aiRatingStatus', 'fusanheDoNotContact', 'fusanheContactPolicy'])
                    ->order('id')->limit($offset, 200)->build();
                $rows = $this->em->getRDBRepository('Lead')->clone($query)->find();
                foreach ($rows as $lead) yield (array) $lead->getValueMap();
                if (count($rows) < 200) break;
            }
        })();
        return $this->json($request, CardProgress::summarize($leads, $now) +
            ['outboundPaused' => ControlService::outboundPaused()]);
    }
}
