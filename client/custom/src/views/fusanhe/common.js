define("custom:views/fusanhe/common", [], function () {
  const labels = {
    heartbeatStale: "心跳超时",
    New: "新线索",
    Assigned: "已分配",
    InProcess: "跟进中",
    Converted: "已转化",
    Recycled: "待再跟进",
    Dead: "无效",
    unknown: "未知",
    healthy: "正常",
    degraded: "异常",
    Alibaba: "阿里国际站",
    MadeInChina: "中国制造网",
    Website: "独立站",
    Email: "邮件",
    Other: "其他",
    new: "新询盘",
    pending: "待回复",
    drafted: "已有草稿",
    waitingApproval: "待审核",
    readyToSend: "待发送",
    sending: "发送中",
    sent: "已发送",
    failed: "失败",
    replied: "已回复",
    closed: "已关闭",
    aiAssist: "AI 辅助",
    human: "人工接管",
    unlinked: "待确认",
    confirmed: "已确认",
    real: "真实",
    mockSent: "模拟已发送",
    generated: "待审核",
    edited: "已修改",
    approved: "已审核",
    rejected: "已拒绝",
    low: "低风险",
    medium: "中风险",
    high: "高风险",
    inbound: "收到",
    outbound: "发出",
    received: "已接收",
    queued: "已排队",
    delivered: "已送达",
    claimed: "已领取",
    cancelled: "已取消",
    draft: "草稿",
    expired: "已过期",
    online: "在线",
    offline: "离线",
    loginExpired: "登录失效",
    captcha: "验证码",
    pageChanged: "页面变化",
    riskControl: "风控",
    active: "启用",
    disabled: "停用",
    mock: "演示",
    website: "独立站",
    email: "邮件",
    alibaba: "阿里国际站",
    madeInChina: "中国制造网",
    notStarted: "未开始",
    inProgress: "进行中",
    completed: "已完成",
    NotStarted: "未开始",
    Started: "进行中",
    Completed: "已完成",
    Deferred: "已延期",
    NotHeld: "未执行",
  };
  // Escape both text and quoted attributes; message previews can contain quotes.
  const escape = (value) =>
    String(value == null || value === "" ? "—" : value).replace(
      /[&<>"']/g,
      (character) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[character],
    );
  const status = (value) => labels[value] || value || "—";
  const badge = (value) =>
    `<span class="fsh-badge ${["failed", "high", "riskControl", "loginExpired"].includes(value) ? "fsh-danger" : ["waitingApproval", "generated", "medium", "captcha", "pageChanged", "heartbeatStale", "human", "mockSent", "unlinked"].includes(value) ? "fsh-warning" : ["sent", "approved", "online", "confirmed"].includes(value) ? "fsh-success" : ""}">${escape(status(value))}</span>`;
  const link = (type, id, name) =>
    id
      ? `<a href="#${type}/view/${encodeURIComponent(id)}">${escape(name)}</a>`
      : escape(name);
  const wait = (value) =>
    value
      ? Math.max(
          0,
          Math.floor(
            (Date.now() - Date.parse(value.replace(" ", "T") + "Z")) / 60000,
          ),
        )
      : null;
  // The outbound notice reflects the live FUSANHE_OUTBOUND_PAUSED switch
  // (cached 60s); it never asserts a state it has not verified.
  let outboundState = null;
  let outboundFetchedAt = 0;
  const pause =
    '<div class="fsh-notice fsh-outbound-notice" role="status">正在获取外发开关状态…</div>';
  const noticeText = (state) =>
    state === true
      ? "系统当前处于全局停发状态：批准只创建发送任务，不会实际发送。"
      : state === false
        ? "全局停发已关闭：批准的任务可被执行端领取并实际发送。"
        : "外发开关状态未知（无法读取状态接口），请勿假定任务不会实际发送。";
  const refreshOutboundNotice = (view) => {
    const root = view.element || view.$el?.[0];
    if (!root) return;
    const apply = (state) => {
      root.querySelectorAll(".fsh-outbound-notice").forEach((el) => {
        el.textContent = noticeText(state);
      });
    };
    apply(outboundState);
    const now = Date.now();
    if (outboundFetchedAt && now - outboundFetchedAt < 60000) return;
    outboundFetchedAt = now;
    if (!view.getAcl?.().checkScope?.("ExternalConversation", "read")) {
      outboundState = null;
      apply(outboundState);
      return;
    }
    require(["ajax"], (Ajax) => {
      Ajax.getRequest("Fusanhe/status")
        .then((r) => {
          outboundState = typeof r?.outboundPaused === "boolean" ? r.outboundPaused : null;
        })
        .catch(() => {
          outboundState = null;
        })
        .then(() => apply(outboundState));
    });
  };
  // Translate only known UI labels; never transform message or editable draft bodies.
  const localize = (view) => {
    const root = view.element || view.$el?.[0];
    if (!view.getLanguage || !root) return;
    const language = view.getLanguage();
    const translate = (text) =>
      language.has(text, "labels", "Fusanhe")
        ? language.translate(text, "labels", "Fusanhe")
        : text;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      if (
        node.parentElement.closest(
          "textarea, .fsh-message-body, .fsh-summary, script, style",
        )
      )
        continue;
      const text = node.nodeValue.trim();
      let replacement = translate(text);
      if (/^\d+(\.\d+)? 分钟$/.test(text))
        replacement = text.replace("分钟", translate("分钟"));
      if (text.startsWith("英文回复草稿 · ") && translate("英语") !== "英语")
        replacement = "Reply draft · " + translate(text.slice(9));
      if (replacement !== text)
        node.nodeValue = node.nodeValue.replace(text, replacement);
    }
    root
      .querySelectorAll("[placeholder], [title], [aria-label]")
      .forEach((el) => {
        ["placeholder", "title", "aria-label"].forEach((attr) => {
          if (el.hasAttribute(attr))
            el.setAttribute(attr, translate(el.getAttribute(attr)));
        });
      });
  };
  return { escape, status, badge, link, wait, pause, outboundState: () => outboundState, refreshOutboundNotice, localize };
});
