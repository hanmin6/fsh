<?php
namespace Espo\Custom\Tools\Fusanhe\Api;
use Espo\Core\Api\{Action, Request, Response, ResponseComposer};
use Espo\Core\Exceptions\NotFound;
use Espo\Custom\Tools\Fusanhe\MediaStorage;
/** Anonymous provider fetch; an unpredictable expiring token is the only authority. */
final class GetCreativeSourceFile implements Action
{
    public function __construct(private MediaStorage $storage) {}
    public function process(Request $request): Response
    {
        try {$file = $this->storage->sharedSource((string) $request->getRouteParam('token'));}
        catch (\Throwable) {throw new NotFound('Source image unavailable.');}
        $response = ResponseComposer::empty()->setHeader('Content-Type', $file['mime'])
            ->setHeader('Cache-Control', 'private, no-store')->setHeader('X-Content-Type-Options', 'nosniff')
            ->setHeader('Referrer-Policy', 'no-referrer');
        $response->writeBody($file['bytes']);
        return $response;
    }
}
