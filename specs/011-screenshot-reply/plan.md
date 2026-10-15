# Implementation Plan: 截图帮我回复
**Branch**: `codex/screenshot-reply` | **Date**: 2026-10-15 | **Spec**: [spec.md](spec.md)

## Summary
React 工作台新增 reply 页面；独立、无数据库副作用的 PHP API 分两步调用视觉模型：识别与推荐方向、按方向/自定义生成或改写。沿用原有鉴权及人工草稿接口。

## Technical Context
- TypeScript 5.8 / React 19 / Vite 6，PHP 8 / EspoCRM 10.0.8。
- 不增加生产依赖；cURL 调用 Responses 多模态接口，固定请求并校验 `gpt-6.1-sol`，复用 FUSANHE_TEXT_API_KEY / FUSANHE_TEXT_API_BASE_URL / FUSANHE_TEXT_TIMEOUT；未启用新网关时仅复用旧 AI_ 凭据和端点，模型仍固定。不自动重试或替换模型。
- 临时内容只保留 React 内存。无数据库迁移；保存草稿仅关联会话时可用。
- 图片最多 3 张，4 MiB/张，合计 8 MiB，单图最多 20M 像素、任一边最多 12000。服务端验证真实格式/大小，拒绝 URL。
- 识别文字最多 12000 字符，自定义 1500 字符，输出正文 12000 字符；响应必须经过结构校验。
- 目标为桌面浏览器与 390px 手机；现有 brand/tokens 保留。

## Constitution Check
I: 先完成 spec/plan/tasks；II: 使用用户明确授权提交的截图作为本功能处理输入（本次会话授权优先于仓库对 AI 输入的通用禁止）。不额外读取后台私密资料，不持久化图片，不自动发送，鉴权在服务端执行；III: 新增接口只计算，无工作流状态变更，草稿复用原接口；IV: 行为测试、PHP 验证、构建和合成浏览器验收，真实模型效果单列；V: 可撤销单独新增路由及 UI 构建产物，原发送控制不变。

## Project Structure
- `client/custom/ui/src/reply-assistant.tsx`, `reply-assistant.css`, `reply-domain.ts`: 页面、样式、类型与校验。
- `client/custom/ui/src/main.tsx`, `domain.ts`, `work.tsx`: 导航、路由和会话入口。
- `custom/Espo/Custom/Tools/Fusanhe/ReplyAssistant.php`: 独立服务及 provider 请求，严格输入/输出验证，不使用旧接口 mock 回退。
- `custom/Espo/Custom/Tools/Fusanhe/Api/PostReplyAssistant.php`, `Resources/routes.json`: authenticated POST，AIReplyDraft create 权限，错误脱敏。
- `tests/test_reply_assistant.py`, `tests/php/reply_assistant.php`, frontend domain tests: 契约、边界、provider transport 测试。

## Delivery and rollback
构建至现有 `client/custom/res/workspace/`。部署需要安装本改动并执行 EspoCRM rebuild；本次用户已授权验证后部署、上传 GitHub 并合并。撤销新增路由和页面并重新构建即可回退；不迁移数据。PHP body/request limit需容纳约 12 MiB JSON。未配置模型返回明确 unavailable，不返回模拟结果。

## Analysis
FR-001–010 均映射任务。PHP 行为和真实 HTTP 验收在隔离 Docker 环境执行；生产模型另用合成截图实测，证据见 verification.md。
