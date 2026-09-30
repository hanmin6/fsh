# CRM Web 1.0.0 验证

日期：2026-09-30。专用 worktree，基于 bd4a2c8；所有界面与运行时测试使用虚构数据。

## 已通过

- TypeScript 检查、Vite 生产构建；包含发布 JS/CSS 和 1.0.0 锁文件。
- 工作台领域测试 12 项：成功证据、未知状态、登录故障、平台独立性、保留成功时间、丢失心跳、无效时间、成功记录过期、消息来源、证书日期、跟进排序、附件元数据。
- 原生前端 Node 测试 13 项：审核状态、风险确认、保存/退回不创建发送、身份和交接 ACL、HTML/附件安全、首页读取。
- `make spec-check SPECIFY_FEATURE_DIRECTORY=specs/005-unified-crm-web`。
- `make verify-offline` 45 项；MIC/Alibaba 离线同步契约另 39 项。
- 自定义 PHP 全量语法检查。隔离 EspoCRM 10.0.8 metadata rebuild 与 app-check 均通过。
- 隔离运行时 39 项：历史信号/证据/权限、Alibaba 幂等同步、客户评级依据与服务器确认字段、防篡改、双平台洞察筛选、商品规格版本、证书状态机、已有安全回归。食品 Feature Flag 在隔离测试中启用。
- Python Playwright 桌面 1440×1000、手机 390×844：独立状态、异常展开/手动收起/恢复、再次异常自动展开、检查失败保留红色、审批勾选及批准后只读、接管、交接、评级、知识库与创作子标签、手机聊天宽度；浏览器未捕获 JS 异常。
- 生产 IIFE 在隔离 Espo 原生宿主内登录加载，客户列表/双平台洞察实际读取成功；旧 service/insights 路由进入统一工作台。

## 重现

前端用 `npm ci --prefix client/custom/ui`、`npm test --prefix client/custom/ui`、`npm run build --prefix client/custom/ui`，以及 `node --test client/custom/tests/frontend.test.cjs`。

浏览器启动 ui 目录下 Vite 的 5176 loopback 端口，再在仓库根目录运行 `python3 tests/unified_ui_browser.py`。需要 Python Playwright 与 Chrome 或已安装的 Playwright Chromium；输出在忽略的 test-results/unified-ui。

运行时复制 `.env.test.example` 为忽略的 `.env.test`，使用测试凭据，把端口/站点设为 18082，启动 `docker compose -p fusanhe-ui-v1-test --env-file .env.test -f tests/unified-ui-compose.yaml up -d --wait`。rebuild 并用相同测试环境 bootstrap，导出 `ESPOCRM_API_URL=http://localhost:18082/api/v1`、测试管理员和 Agent 凭据，设置 `COMPOSE_PROJECT_NAME=fusanhe-ui-v1-test`、`COMPOSE_FILE=tests/unified-ui-compose.yaml`、`COMPOSE_ENV_FILES=.env.test`、`RUN_BOSS_INSIGHTS_RUNTIME=1`、`RUN_ALIBABA_SYNC_RUNTIME=1`、`RUN_UNIFIED_CRM_RUNTIME=1`，再运行：

```bash
python3 -m unittest tests.test_boss_insights tests.test_boss_insights_runtime tests.test_alibaba_sync_runtime tests.test_unified_crm_runtime tests.test_wp1_products tests.test_wp2_certificates tests.test_security_regression
```

初次测试曾指向未运行的默认 stack；一项旧测试写死项目名，现改为支持 COMPOSE_PROJECT_NAME/COMPOSE_FILE。新增平台 fixture 补齐 externalId/accountHandle 后，全套重跑通过。记录这些环境修正，不将初次失败作为已通过结果。

## 实际边界

未调用真实图片/视频供应商，未发送客户消息，未做生产部署或真实平台账号完整抓取验收。抓取依据是已报告的成功同步及心跳，未报告的空轮询无法证明成功；超时和未知可见。公开共享账号免登录的专用运行时套件本次未启用，本版没有更改认证实现或扩权。

完整设计的媒体生成、实际视频下载/关联、来源平台原始附件下载及完整采集历史依赖外部服务/采集报告，本版保留明确可用状态和入口；不声称这些外部服务已接通。真实供应商接入沿用本版 UI。

## GitHub 发布验证

[PR #1](https://github.com/hanmin6/fsh/pull/1) 的核心提交 `8baa2ed6d2024ad104cc00816f00aa516afdb9dd` 已通过 [GitHub Actions verify #20](https://github.com/hanmin6/fsh/actions/runs/36668511534)：前端测试/构建/构建产物一致性/浏览器回归、Spec/Python/PHP 与 Android 测试/lint/组装均成功。PR 已合入 main（合并提交 `483dc510e6ffb81f9411077618bda9e9497dd234`）。

五个 archive 标签在删除旧 Web 远程分支前已逐项核对到精确原提交；三条旧 Web 远程分支已经删除，活跃本地 worktree 和未提交文件保留。最后的文档完成提交与 crm-web-v1.0.0 标签通过同一次原子 push 发布到 main。临时整合远程分支发布后删除。
