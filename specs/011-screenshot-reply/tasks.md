# Tasks: 截图帮我回复
## Phase 1: Setup
- [x] T001 建立需求、架构和契约，FR-001–010，`specs/011-screenshot-reply/`。
## Phase 2: Foundation
- [x] T002 增加边界/错误/结构测试，FR-007–010，`tests/php/reply_assistant.php`、`tests/test_reply_assistant.py`。
- [x] T003 实现无状态视觉模型服务、图片验证和 ACL API，FR-002/007–009，`custom/Espo/Custom/Tools/Fusanhe/ReplyAssistant.php`、`Api/PostReplyAssistant.php`、`Resources/routes.json`。
## Phase 3: US1
- [x] T004 [US1] 实现导航和截图上传/粘贴/拖放/删除、可编辑识别与三方向，FR-001–003，`client/custom/ui/src/reply-assistant.tsx`、`reply-domain.ts`、`main.tsx`、`domain.ts`。
## Phase 4: US2
- [x] T005 [US2] 实现自定义、语言、生成/改写/编辑/复制、重试及状态失效，FR-004/005/008，`client/custom/ui/src/reply-assistant.tsx`。
- [x] T006 [US2] 实现桌面/移动响应布局与交互测试，SC-001–004，`client/custom/ui/src/reply-assistant.css`、`reply-domain.test.ts`。
## Phase 5: US3
- [x] T007 [US3] 接入会话带入、原草稿保存和权限检查，FR-006/007，`client/custom/ui/src/work.tsx`、`reply-assistant.tsx`。
## Phase 6: Verification
- [x] T008 执行构建/契约/PHP/浏览器验收，独立设计复核，记录范围与限制，FR-010，`specs/011-screenshot-reply/verification.md`。

## Dependencies and strategy
T001 -> T002/T003 -> T004 -> T005/T006 -> T007 -> T008；按截图识别、生成、会话关联逐层验证。测试与独立样式文件可并行，当前逐项完成。生产模型和部署验证单独记录，不把合成验证作为真实效果证据。
