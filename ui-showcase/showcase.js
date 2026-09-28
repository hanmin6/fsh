(() => {
  'use strict';

  const fixture = window.showcaseFixtures;
  const runtime = window.FusanheUIRuntime;
  const mount = document.getElementById('showcase-mount');
  const catalog = document.getElementById('showcase-catalog');
  const navigation = document.getElementById('showcase-navigation');
  const notice = document.getElementById('showcase-notice');
  const breadcrumb = document.getElementById('showcase-breadcrumb');
  let handle = null;
  let toastTimer;

  const groups = [
    ['工作台', [
      ['首页', '#Home', 'home'], ['CRM 工作台', '#Home/crm', 'crm'],
      ['AI 客服工作台', '#Home/service', 'service'], ['历史客户与建议', '#Home/insights', 'insights'],
    ]],
    ['业务队列', [
      ['统一询盘', '#ExternalConversation', 'queue'], ['AI 草稿', '#AIReplyDraft', 'queue'],
      ['知识文档', '#KnowledgeDocument', 'queue'], ['发送任务', '#OutboundTask', 'queue'],
      ['平台执行端', '#AutomationAgent', 'queue'],
    ]],
    ['记录详情', [
      ['会话工作台', '#ExternalConversation/view/v1', 'conversation'],
      ['客户公司', '#Account/view/a1', 'customer-detail'],
      ['联系人', '#Contact/view/c1', 'customer-detail'],
      ['销售线索', '#Lead/view/l1', 'customer-detail'],
      ['草稿业务提示', '#AIReplyDraft/view/d1', 'context-detail'],
      ['知识资料提示', '#KnowledgeDocument/view/k1', 'context-detail'],
      ['发送任务提示', '#OutboundTask/view/o1', 'context-detail'],
    ]],
    ['其他界面', [
      ['登录页', '#showcase/login', 'catalog'],
      ['Espo 原生页面', '#showcase/native', 'catalog'],
      ['Android 页面', '#showcase/android', 'catalog'],
    ]],
  ];

  function toast(message) {
    const node = document.getElementById('showcase-toast');
    node.textContent = message;
    node.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { node.hidden = true; }, 3200);
  }

  function whereMatches(row, condition) {
    if (!condition || !condition.attribute && condition.type !== 'or') return true;
    if (condition.type === 'or') return (condition.value || []).some(item => whereMatches(row, item));
    const actual = row[condition.attribute];
    if (condition.type === 'equals') return actual === condition.value;
    if (condition.type === 'in') return (condition.value || []).includes(actual);
    if (condition.type === 'notIn') return !(condition.value || []).includes(actual);
    if (condition.type === 'isNull') return actual == null || actual === '';
    if (condition.type === 'greaterThan') return Number(actual) > Number(condition.value);
    if (condition.type === 'before') return String(actual || '') < String(condition.value || '');
    if (condition.type === 'contains') return String(actual || '').toLowerCase().includes(String(condition.value || '').toLowerCase());
    return true;
  }

  function listFor(entity, params = {}) {
    let rows = (fixture[entity] || []).map(row => ({ ...row }));
    for (const condition of params.where || []) rows = rows.filter(row => whereMatches(row, condition));
    if (params.textFilter) {
      const query = String(params.textFilter).toLowerCase();
      rows = rows.filter(row => Object.values(row).some(value => String(value ?? '').toLowerCase().includes(query)));
    }
    if (params.orderBy) {
      rows.sort((a, b) => String(a[params.orderBy] || '').localeCompare(String(b[params.orderBy] || '')));
      if (params.order === 'desc') rows.reverse();
    }
    const total = rows.length;
    const offset = Math.max(0, Number(params.offset) || 0);
    const size = Number(params.maxSize) || rows.length;
    return { total, list: rows.slice(offset, offset + size) };
  }

  function insights(params = {}) {
    let rows = fixture.ExternalConversation.map(row => ({
      id: row.id, name: row.name, externalId: row.externalId, owner: row.assignedUserName,
      lastMessageAt: row.lastMessageAt, needsManualMatch: row.needsManualMatch,
      customer: { type: 'Account', id: row.accountId },
      analysisStatus: row.id === 'v1' ? 'pending' : 'completed',
    }));
    if (params.q) rows = rows.filter(row => `${row.name} ${row.externalId}`.toLowerCase().includes(String(params.q).toLowerCase()));
    if (params.status) rows = rows.filter(row => row.analysisStatus === params.status);
    return {
      date: '2026-09-28', timezone: 'Asia/Shanghai', outboundPaused: true, scope: 'all',
      coverage: { platformVisible: null, imported: 2, failedSync: null, pendingIdentity: 1,
        analysisCompleted: 1, analysisFailed: 0, analysisStale: 0, reconciled: false,
        reason: '待采集端提供完整分页及消息对账；平台可见总数和未入库失败数未知。仅统计带同步来源的 Alibaba 会话。' },
      suggestions: [{ id: 'v1', name: fixture.ExternalConversation[0].name, priority: 1,
        reason: '身份尚未确认', action: '核对平台身份与客户关联后再跟进', owner: '演示业务员' }],
      suggestionTotal: 1, total: rows.length, offset: Number(params.offset) || 0, limit: 25,
      list: rows.slice(Number(params.offset) || 0, (Number(params.offset) || 0) + 25),
    };
  }

  const host = {
    api: {
      get: async (route, params = {}) => {
        if (route === 'Fusanhe/insights') return insights(params);
        if (route.startsWith('Fusanhe/insights/')) {
          const id = decodeURIComponent(route.split('/').at(-1));
          const row = insights().list.find(item => item.id === id);
          return row ? { ...row, analysis: { summaryZh: '示例数据：客户询问产品规格。', demand: '规格与交期',
            products: ['冷冻蓝莓'], historyProgress: '仍待业务员核查', latestStatus: '待回复',
            buyingSignals: ['询问规格'], risks: ['身份未确认'], missingFacts: ['目的港'], nextAction: '人工核实需求' },
            analysisNotice: '匿名信号分析，业务事实请核对原文。', evidence: [{ id: 'm1', direction: 'inbound', sentAt: '2026-09-26 08:31:00' }] } : null;
        }
        if (route.includes('/handoff-tasks')) return { tasks: [] };
        if (route.startsWith('Fusanhe/')) return {};
        const slash = route.indexOf('/');
        if (slash > 0) {
          const entity = route.slice(0, slash), id = decodeURIComponent(route.slice(slash + 1));
          return (fixture[entity] || []).find(row => row.id === id) || null;
        }
        return listFor(route, params);
      },
      post: async () => { throw new Error('展示模式禁止写入'); },
      patch: async () => { throw new Error('展示模式禁止写入'); },
    },
    can: (_scope, action = 'read') => action === 'read',
    navigate: hash => { location.hash = hash; },
    translate: label => label,
    notify: message => toast(message),
    currentUserId: 'u1',
    getOutboundState: async () => ({ paused: true, status: 'paused' }),
  };

  function nativeCatalog() {
    const rows = [
      ['登录与品牌', 'client/custom/src/views/fusanhe/login.js', 'Espo 登录宿主 + brand.css'],
      ['原生实体列表/详情/编辑', 'client/custom/res/fusanhe/native.css', 'Account、Contact、Lead、Task 与食品业务实体'],
      ['客户/联系人/线索概览', 'client/custom/ui/src/screens/customer/detail.tsx', '原版 React 概览可从左侧打开；下方关系面板需 Espo'],
      ['知识文档、发送任务、草稿', 'client/custom/ui/src/screens/customer/context.tsx', '原版 React 提示可从左侧打开；记录字段需 Espo'],
      ['运营概览 Dashlet', 'client/custom/src/views/dashlets/fusanhe-operations.js', '依赖 Espo Dashlet 宿主'],
      ['食品外贸实体布局', 'custom/Espo/Custom/Resources/layouts/', '产品、证书、样品、报价、订单、交付'],
    ];
    return `<div class="showcase-catalog"><h1>Espo 原生页面</h1><p>这些页面由 EspoCRM 的路由、元数据、表单和关系面板组合，无法仅加载 React 构建产物得到原样页面。下表列出源码入口；完整视觉验收需运行 CRM。</p><table><thead><tr><th>界面</th><th>源码入口</th><th>预览边界</th></tr></thead><tbody>${rows.map(([label, path, note]) => `<tr><td>${label}</td><td><a href="../${path}" target="_blank" rel="noopener">${path}</a></td><td>${note}</td></tr>`).join('')}</tbody></table></div>`;
  }

  function androidCatalog() {
    const base = 'android-client/app/src/main/java/com/fusanhe/crm/ui/screens/';
    const rows = [
      ['启动', 'splash/SplashScreen.kt'], ['登录', 'login/LoginScreen.kt'],
      ['工作台', 'dashboard/DashboardScreen.kt'], ['客户列表', 'customers/CustomerListScreen.kt'],
      ['客户搜索', 'customersearch/CustomerSearchScreen.kt'],
      ['新增客户', 'addcustomer/AddCustomerScreen.kt'], ['客户详情', 'customerdetail/CustomerDetailScreen.kt'],
      ['询盘列表', 'conversations/ConversationListScreen.kt'], ['会话与 AI 建议', 'chat/ChatScreen.kt'],
      ['翻译与 AI 弹层', 'chat/ChatSheets.kt'], ['通知', 'notifications/NotificationsScreen.kt'],
      ['个人中心', 'profile/ProfileScreen.kt'], ['设置', 'settings/SettingsScreen.kt'],
    ];
    return `<div class="showcase-catalog"><h1>Android Compose 页面</h1><p>Android 界面保留在独立原生项目中。当前没有可用模拟器或仓库内的原版页面截图，因此这里只做准确的页面与源码目录；浏览器页面不会冒充 Android 真机画面。</p><table><thead><tr><th>页面</th><th>源码</th></tr></thead><tbody>${rows.map(([label, path]) => `<tr><td>${label}</td><td><a href="../${base}${path}" target="_blank" rel="noopener">${path}</a></td></tr>`).join('')}</tbody></table><p><a href="../android-client/README.md" target="_blank" rel="noopener">Android 构建与演示说明</a></p></div>`;
  }

  function loginCatalog() {
    return `<div class="showcase-catalog"><h1>登录页</h1><p>以下为原版 Logo 与登录结构的静态展示。真实登录视图由 EspoCRM 渲染，认证和错误状态需在 CRM 环境验收。</p><div class="showcase-login"><img src="../client/custom/res/fusanhe/logo-full.png" alt="福三和"><label for="demo-user">用户名</label><input id="demo-user" value="演示账号" readonly><label for="demo-password">密码</label><input id="demo-password" type="password" readonly><button type="button" disabled>登录（展示模式）</button><small>展示模式不会提交账号或密码。</small></div><p>源码：<a href="../client/custom/src/views/fusanhe/login.js" target="_blank" rel="noopener">login.js</a> · <a href="../client/custom/res/fusanhe/brand.css" target="_blank" rel="noopener">brand.css</a></p></div>`;
  }

  function routeInfo(hash) {
    const value = decodeURIComponent((hash || '#Home').replace(/^#/, ''));
    if (value === 'Home') return { screen: 'home', label: '首页' };
    if (value === 'Home/crm') return { screen: 'crm', label: 'CRM 工作台' };
    if (value === 'Home/service') return { screen: 'service', label: 'AI 客服工作台' };
    if (value === 'Home/insights') return { screen: 'insights', label: '历史客户与建议' };
    if (value === 'showcase/login') return { catalog: 'login', label: '登录页' };
    if (value === 'showcase/native') return { catalog: 'native', label: 'Espo 原生页面' };
    if (value === 'showcase/android') return { catalog: 'android', label: 'Android 页面' };
    const detail = value.match(/^([^/]+)\/view\/([^/?]+)/);
    if (detail) {
      const [, entity, id] = detail;
      if (entity === 'ExternalConversation') return { screen: 'conversation', label: '会话工作台', data: { conversationId: id } };
      if (['Account', 'Contact', 'Lead'].includes(entity)) return { screen: 'customer-detail', label: `${entity} 业务概览`, data: { type: entity, id, attributes: fixture[entity]?.find(row => row.id === id) || {} } };
      if (['AIReplyDraft', 'KnowledgeDocument', 'OutboundTask'].includes(entity)) return { screen: 'context-detail', label: `${entity} 业务提示`, data: { type: entity, conversationId: 'v2', riskLevel: entity === 'AIReplyDraft' ? 'high' : 'low' } };
      return { catalog: 'native', label: `${entity} 原生页面` };
    }
    if (['ExternalConversation', 'AIReplyDraft', 'KnowledgeDocument', 'OutboundTask', 'AutomationAgent'].includes(value)) {
      return { screen: 'queue', label: value, data: { entity: value, statusOptions: { ExternalConversation: ['new', 'pending', 'waitingApproval', 'replied'], AIReplyDraft: ['generated', 'edited', 'approved'], KnowledgeDocument: ['draft', 'approved', 'expired'], OutboundTask: ['pending', 'failed', 'sent'], AutomationAgent: ['online', 'offline'] }[value] } };
    }
    return { catalog: 'native', label: value };
  }

  function render() {
    const info = routeInfo(location.hash);
    if (handle) { runtime.unmount(handle); handle = null; }
    breadcrumb.textContent = `${info.catalog === 'android' ? 'Android' : 'Web'} / ${info.label}`;
    document.querySelectorAll('.showcase-nav').forEach(button => button.classList.toggle('active', button.dataset.hash === (location.hash || '#Home')));
    document.getElementById('showcase-side').classList.remove('open');
    if (info.catalog) {
      mount.hidden = true;
      catalog.hidden = false;
      catalog.innerHTML = info.catalog === 'login' ? loginCatalog() : info.catalog === 'android' ? androidCatalog() : nativeCatalog();
      notice.textContent = '目录页标明了无法在静态浏览器中原样运行的界面及其源码入口。';
    } else {
      catalog.hidden = true;
      mount.hidden = false;
      notice.textContent = '页面主体直接运行仓库内的原版 React 组件；虚构数据只读，所有写入被拦截，全局外发保持关闭。';
      handle = runtime.mount(mount, info.screen, host, info.data || {});
    }
    window.scrollTo(0, 0);
  }

  for (const [group, items] of groups) {
    const heading = document.createElement('div');
    heading.className = 'showcase-group';
    heading.textContent = group;
    navigation.appendChild(heading);
    for (const [label, hash] of items) {
      const button = document.createElement('button');
      button.type = 'button'; button.className = 'showcase-nav'; button.textContent = label; button.dataset.hash = hash;
      button.onclick = () => { if (location.hash === hash) render(); else location.hash = hash; };
      navigation.appendChild(button);
    }
  }
  document.getElementById('showcase-menu').onclick = () => document.getElementById('showcase-side').classList.toggle('open');
  window.addEventListener('hashchange', render);
  if (!runtime || !fixture) {
    mount.textContent = '原版组件或示例数据未加载。请从仓库根目录启动本地静态服务器。';
  } else {
    render();
  }
})();
