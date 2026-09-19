<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Core\Exceptions\BadRequest;
use Espo\Core\Exceptions\Conflict;

final class PostProductSpecRetire extends AbstractFusanheAction
{
    public function process(Request $request): Response
    {
        $this->requireFeature('products');
        $this->requireScope('FusanheProductSpec', 'edit');
        $id = $request->getRouteParam('id');
        if (!$id) throw new BadRequest();
        $spec = $this->requireEntity('FusanheProductSpec', $id);
        if ($spec->get('status') === 'retired') {
            throw new Conflict('Spec version is already retired.');
        }
        $spec->set('status', 'retired');
        $this->em->saveEntity($spec);
        return ResponseComposer::json(['id' => $spec->getId(), 'status' => 'retired']);
    }
}
