<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Core\Acl;
use Espo\Core\Exceptions\Forbidden;
use Espo\Custom\Tools\Fusanhe\KnowledgeScanner;

/** Scanning rewrites knowledge documents, so it needs document edit rights. */
final class PostKnowledgeScan implements Action
{
    public function __construct(
        private KnowledgeScanner $scanner,
        private Acl $acl,
    ) {}

    public function process(Request $request): Response
    {
        if (!$this->acl->checkScope('KnowledgeDocument', 'edit')) {
            throw new Forbidden('Not allowed to scan knowledge documents.');
        }
        return ResponseComposer::json($this->scanner->scan());
    }
}
