# AI 获得客资入口

2026-10-12 已部署至 https://crm.fsh.digital/ 。

- 左侧导航新增「AI获得客资」，首页「主动获客AI」新增同名入口。
- 两处均打开 `workspace=acquisition` 客资列表，支持搜索、来源、评级、跟进分流筛选与分页。点击客户或「查看资料」打开既有 Lead 详情。
- 仅显示 Muse、Xpoz、OpenOutreach 入库且存在来源 ID 的 Lead，沿用 Lead 读取权限。历史 Muse 导入按来源 ID 中保留的 Xpoz/OpenOutreach 前缀显示与筛选实际来源。
- 线上验证：总数 8，Xpoz 6，OpenOutreach 2；人工分流筛选正确显示空状态，客户详情正常打开。
- 前端 TypeScript/Vite 构建通过，现有 18 项测试通过，git diff --check 通过。
- 只发布 workspace.js/workspace.css，发布前备份，更新 appTimestamp。部署清单见 deployments/outreach-22005/records/acquisition-ui-20261012.json。
- 本次为入口与查询页面改造，不改变获客执行、发送渠道和自动回复逻辑。

截图：test-results/acquisition-ui/home-online.jpg、leads-online.jpg。
