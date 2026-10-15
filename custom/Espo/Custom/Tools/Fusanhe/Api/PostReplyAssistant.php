<?php
namespace Espo\Custom\Tools\Fusanhe\Api;

use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Custom\Tools\Fusanhe\ReplyAssistant;

// Non-2xx bodies are normalized by FusanheApiMiddleware; clients use HTTP status.
final class PostReplyAssistant extends AbstractFusanheAction
{
    public function process(Request $request): Response
    {
        $this->requireScope('AIReplyDraft', 'create');
        $body = $request->getParsedBody();
        try {
            // Convert nested parsed objects while retaining all validation in the service.
            $input = json_decode(json_encode($body, JSON_THROW_ON_ERROR), true, 32, JSON_THROW_ON_ERROR);
            if (!is_array($input)) throw new \InvalidArgumentException();
            $result = (new ReplyAssistant())->handle($input);
            return $this->json($request, ['ok' => true, 'result' => $result]);
        } catch (\InvalidArgumentException | \JsonException $error) {
            return $this->json($request, ['ok' => false, 'error' => 'invalid_request', 'message' => '请检查输入：最多 3 张 PNG、JPG 或 WebP 图片，每张不超过 4 MB，总计不超过 8 MB；聊天内容和回复要求不能为空或超长。'], 400);
        } catch (\UnexpectedValueException $error) {
            return $this->json($request, ['ok' => false, 'error' => 'invalid_ai_response', 'message' => 'AI 返回的内容不完整，请重试；也可以补充更清晰的聊天文字。'], 502);
        } catch (\Throwable $error) {
            // Never echo provider bodies, exception messages, credentials or screenshot data.
            $missing = !ReplyAssistant::configured();
            return $this->json($request, ['ok' => false, 'error' => $missing ? 'ai_not_configured' : 'ai_unavailable', 'message' => $missing ? '尚未配置 AI 服务，请联系管理员配置支持图片识别的模型。' : 'AI 服务暂时不可用，请稍后重试；管理员可检查模型是否支持图片和 JSON 输出。'], $missing ? 503 : 502);
        }
    }
}
