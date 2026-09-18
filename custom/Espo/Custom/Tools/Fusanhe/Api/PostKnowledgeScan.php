<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Custom\Tools\Fusanhe\KnowledgeScanner;
final class PostKnowledgeScan implements Action { public function __construct(private KnowledgeScanner $scanner) {} public function process(Request $request): Response {return ResponseComposer::json($this->scanner->scan());} }
