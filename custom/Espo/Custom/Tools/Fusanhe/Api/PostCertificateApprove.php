<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Core\Exceptions\BadRequest;
use Espo\Core\Exceptions\Conflict;

final class PostCertificateApprove extends AbstractFusanheAction
{
    public function process(Request $request): Response
    {
        $this->requireFeature('certificates');
        $this->requireScope('FusanheCertificate', 'edit');
        $id = $request->getRouteParam('id');
        if (!$id) throw new BadRequest();
        $cert = $this->requireEntity('FusanheCertificate', $id);
        if ($cert->get('status') !== 'draft') {
            throw new Conflict('Only draft certificates can be approved.');
        }
        $cert->set(['status' => 'approved', 'reviewerId' => $this->user->getId(), 'reviewedAt' => gmdate('Y-m-d H:i:s')]);
        $this->em->saveEntity($cert);
        return ResponseComposer::json(['id' => $cert->getId(), 'status' => 'approved']);
    }
}
