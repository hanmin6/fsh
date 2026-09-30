<?php
namespace Espo\Custom\Tools\Fusanhe;

/** TokenDance documented image-generations + MiniMax video V2 protocols. */
class MediaGateway
{
    public function __construct(private MediaNetwork $network) {}
    private function base(): string { return rtrim((string) (getenv('FUSANHE_MEDIA_API_BASE_URL') ?: 'https://tokendance.space/gateway/v1'), '/'); }
    private function key(): string { return trim((string) getenv('FUSANHE_MEDIA_API_KEY')); }
    private function imageModel(): string { return trim((string) getenv('FUSANHE_MEDIA_IMAGE_MODEL')); }
    private function videoModel(): string { return trim((string) getenv('FUSANHE_MEDIA_VIDEO_MODEL')); }
    public function status(): array
    {
        $configured = $this->key() !== '' && $this->base() === 'https://tokendance.space/gateway/v1';
        $enabled = filter_var(getenv('FUSANHE_MEDIA_ENABLED') ?: 'false', FILTER_VALIDATE_BOOL);
        // Allow-listed catalog IDs with documented protocols; arbitrary aliases fail closed.
        $image = false; // User explicitly deferred image generation for this release.
        $video = $configured && $enabled && in_array($this->videoModel(), ['minimax-h3-max', 'minimax-h3'], true);
        return ['provider' => 'tokendance', 'configured' => $configured, 'enabled' => $enabled,
            'capabilities' => ['image' => $image, 'video' => $video], 'imageModel' => $this->imageModel() ?: null,
            'videoModel' => $this->videoModel() ?: null, 'reason' => $image || $video ? null : 'media_unavailable',
            'videoSource' => 'public_url_or_text', 'imageSource' => 'text_only', 'cost' => null, 'healthChecked' => false];
    }
    public function validateSourceUrl(string $url): void { $this->network->publicUrl($url); }
    public function submit(string $kind, string $prompt, string $sourceUrl, array $preferences, string $idempotencyKey): array
    {
        if (!($this->status()['capabilities'][$kind] ?? false)) throw new \RuntimeException('media_unavailable');
        if ($kind === 'image') {
            // This protocol creates images from text; uploaded sources are never claimed to be image edits.
            $result = $this->network->json('POST', $this->base() . '/images/generations', $this->key(),
                ['model' => $this->imageModel(), 'prompt' => $prompt, 'n' => 1, 'size' => '1024x1024']);
            $url = $result['data'][0]['url'] ?? null;
            if (!is_string($url)) throw new \RuntimeException('media_invalid_response');
            return ['status' => 'completed', 'model' => $this->imageModel()] + $this->network->download($url, 'image');
        }
        $content = [['type' => 'text', 'text' => $prompt]];
        if ($sourceUrl !== '') { $this->validateSourceUrl($sourceUrl); $content[] = ['type' => 'image_url', 'image_url' => ['url' => $sourceUrl], 'role' => 'first_frame']; }
        $body = ['model' => $this->videoModel(), 'resolution' => '768P', 'duration' => (int) $preferences['duration'], 'content' => $content];
        if ($sourceUrl === '') $body['ratio'] = $preferences['aspect'];
        $result = $this->network->json('POST', 'https://tokendance.space/gateway/minimax/v2/video_generation', $this->key(), $body);
        $remote = $result['task_id'] ?? null;
        if (!is_string($remote) || !preg_match('/^[A-Za-z0-9._:-]{1,255}$/D', $remote)) throw new \RuntimeException('media_invalid_response');
        return ['status' => 'queued', 'providerJobId' => $remote, 'model' => $this->videoModel()];
    }
    public function reconcile(string $providerJobId, string $kind): array
    {
        if ($kind !== 'video' || !preg_match('/^[A-Za-z0-9._:-]{1,255}$/D', $providerJobId) || !($this->status()['capabilities']['video'] ?? false)) throw new \RuntimeException('media_reconciliation_unavailable');
        $result = $this->network->json('GET', 'https://tokendance.space/gateway/minimax/v2/query/video_generation/' . rawurlencode($providerJobId), $this->key());
        $task = $result['task'] ?? [];
        $status = match ($task['status'] ?? null) { 'queued' => 'queued', 'running' => 'processing', 'succeeded' => 'completed', 'failed', 'cancelled', 'expired' => 'failed', default => throw new \RuntimeException('media_invalid_response') };
        $value = ['status' => $status, 'providerJobId' => $providerJobId];
        if ($status === 'completed') {
            $url = $task['content']['url'] ?? null;
            if (!is_string($url)) throw new \RuntimeException('media_invalid_response');
            $value += $this->network->download($url, 'video/mp4');
        }
        return $value;
    }
}
