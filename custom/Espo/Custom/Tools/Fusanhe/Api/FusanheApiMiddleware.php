<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Exceptions\BadRequest;
use Espo\Core\Exceptions\Conflict;
use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Exceptions\NotFound;
use Espo\Core\Exceptions\Unauthorized;
use Psr\Http\Message\ResponseInterface;
use Psr\Http\Message\ServerRequestInterface;
use Psr\Http\Server\MiddlewareInterface;
use Psr\Http\Server\RequestHandlerInterface;
use Slim\Psr7\Factory\ResponseFactory;

/** Request tracing and fail-closed public errors for the Fusanhe API only. */
final class FusanheApiMiddleware implements MiddlewareInterface
{
    public function process(ServerRequestInterface $request, RequestHandlerInterface $handler): ResponseInterface
    {
        if (!str_contains($request->getUri()->getPath(), '/Fusanhe/')) {
            return $handler->handle($request);
        }

        $requestId = $this->requestId($request->getHeaderLine('X-Request-Id'));
        RequestContext::set($requestId);
        try {
            $response = $handler->handle($request);
            if ($response->getStatusCode() >= 400) {
                return $this->errorResponse($response->getStatusCode(), $this->codeForStatus($response->getStatusCode()), $requestId);
            }
            return $response->withHeader('X-Request-Id', $requestId);
        } catch (\Throwable $error) {
            [$status, $code] = $this->publicError($error);
            return $this->errorResponse($status, $code, $requestId);
        } finally {
            RequestContext::clear();
        }
    }

    private function requestId(string $incoming): string
    {
        $incoming = trim($incoming);
        if ($incoming !== '' && preg_match('/^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$/', $incoming)) {
            return $incoming;
        }
        return bin2hex(random_bytes(16));
    }

    /** @return array{int, string} */
    private function publicError(\Throwable $error): array
    {
        return match (true) {
            $error instanceof BadRequest => [400, 'invalid_request'],
            $error instanceof Unauthorized => [401, 'unauthorized'],
            $error instanceof Forbidden => [403, 'forbidden'],
            $error instanceof NotFound => [404, 'not_found'],
            $error instanceof Conflict => [409, 'conflict'],
            default => [500, 'internal_error'],
        };
    }

    private function codeForStatus(int $status): string
    {
        return match ($status) {
            400 => 'invalid_request',
            401 => 'unauthorized',
            403 => 'forbidden',
            404 => 'not_found',
            409 => 'conflict',
            default => $status >= 500 ? 'internal_error' : 'request_failed',
        };
    }

    private function errorResponse(int $status, string $code, string $requestId): ResponseInterface
    {
        $response = (new ResponseFactory())->createResponse($status)
            ->withHeader('Content-Type', 'application/json')
            ->withHeader('X-Request-Id', $requestId);
        $response->getBody()->write((string) json_encode([
            'error' => ['code' => $code, 'requestId' => $requestId],
        ], JSON_UNESCAPED_SLASHES));
        return $response;
    }
}
