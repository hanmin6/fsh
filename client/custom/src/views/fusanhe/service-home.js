define("custom:views/fusanhe/service-home", [
  "views/main",
  "ajax",
  "custom:views/fusanhe/common",
], function (Dep, Ajax, U) {
  // AI service workspace: unified inbox, draft review, identity
  // confirmation backlog and send exceptions. Management entries (channels,
  // agents) appear only for roles with read access.
  return class extends Dep {
    templateContent =
      '<div class="fsh-shell"><header class="fsh-header"><div><h1>AI 客服工作台</h1><div class="fsh-subtitle">统一收件箱、草稿审核、身份确认与发送异常</div></div><button class="btn btn-default fsh-refresh">刷新</button></header><div class="fsh-dashboard-body" aria-live="polite"></div></div>';
    updatePageTitle() {
      this.getHelper().pageTitle.setTitle(
        this.translate("AI 客服工作台", "labels", "Fusanhe"),
      );
    }
    afterRender() {
      super.afterRender();
      this.$el.find(".fsh-refresh").on("click", () => this.load());
      this.load();
    }
    async total(entity, where) {
      if (!this.getAcl().checkScope(entity, "read")) return null;
      try {
        const r = await Ajax.getRequest(entity, {
          maxSize: 1,
          where: where ? [where] : [],
        });
        return r.total >= 0 ? r.total : null;
      } catch (e) {
        return null;
      }
    }
    async recent(entity, select, extra) {
      if (!this.getAcl().checkScope(entity, "read")) return null;
      try {
        const r = await Ajax.getRequest(entity, {
          maxSize: 6,
          orderBy: extra?.orderBy || "createdAt",
          order: "desc",
          select: select.join(","),
          where: extra?.where ? [extra.where] : [],
        });
        return r.list || [];
      } catch (e) {
        return null;
      }
    }
    async load() {
      this.$el.find(".fsh-refresh").prop("disabled", true);
      this.$el
        .find(".fsh-dashboard-body")
        .html('<div class="fsh-empty" role="status">正在加载客服数据…</div>');
      const [tOpen, tReply, tReview, tIdentity, tException, tTakeover] =
        await Promise.all([
          this.total("ExternalConversation"),
          this.total("ExternalConversation", {
            type: "in",
            attribute: "status",
            value: ["new", "pending"],
          }),
          this.total("AIReplyDraft", {
            type: "in",
            attribute: "status",
            value: ["generated", "edited"],
          }),
          this.getAcl().checkScope("ExternalIdentity", "read")
            ? this.total("ExternalIdentity", {
                type: "equals",
                attribute: "linkStatus",
                value: "unlinked",
              })
            : null,
          this.total("OutboundTask", {
            type: "in",
            attribute: "status",
            value: ["failed", "sending"],
          }),
          this.total("ExternalConversation", {
            type: "equals",
            attribute: "controlMode",
            value: "human",
          }),
        ]);
      const [conversations, drafts, identities, exceptions, channels, agents] =
        await Promise.all([
          this.recent("ExternalConversation", [
            "id",
            "name",
            "status",
            "controlMode",
            "lastMessagePreview",
            "lastInboundAt",
            "assignedUserName",
            "needsManualMatch",
          ], { orderBy: "lastMessageAt" }),
          this.recent("AIReplyDraft", [
            "id",
            "name",
            "status",
            "conversationId",
            "conversationName",
            "summaryZh",
            "riskLevel",
            "createdAt",
          ]),
          this.getAcl().checkScope("ExternalIdentity", "read")
            ? this.recent("ExternalIdentity", [
                "id",
                "name",
                "channelType",
                "externalUserId",
                "displayName",
                "linkStatus",
                "lastSeenAt",
              ])
            : null,
          this.recent("OutboundTask", [
            "id",
            "name",
            "status",
            "executionMode",
            "errorMessage",
            "conversationId",
            "conversationName",
          ]),
          this.recent("ExternalChannel", [
            "id",
            "name",
            "type",
            "connectionStatus",
          ]),
          this.getAcl().checkScope("AutomationAgent", "read")
            ? this.recent("AutomationAgent", [
                "id",
                "name",
                "status",
                "mode",
                "lastHeartbeatAt",
                "lastError",
              ])
            : null,
        ]);
      const values = [
        ["进行中会话", tReply ?? "—"],
        ["待审核草稿", tReview ?? "—"],
        ["身份待确认", tIdentity === null ? "—" : tIdentity],
        ["人工接管中", tTakeover === null ? "—" : tTakeover],
        ["发送异常", tException ?? "—"],
        ["会话总数", tOpen ?? "—"],
      ];
      const section = (title, entity, rows, cell) =>
        `<section class="fsh-section"><h2>${title}<a href="#${entity}">查看全部</a></h2>${
          rows === null
            ? '<div class="fsh-empty">暂不可用或没有读取权限。</div>'
            : !rows.length
              ? '<div class="fsh-empty">暂无记录。收到相关业务数据后将在这里显示。</div>'
              : `<div class="fsh-table-scroll"><table class="fsh-table"><tbody>${rows
                  .map(cell)
                  .join("")}</tbody></table></div>`
        }</section>`;
      this.$el.find(".fsh-dashboard-body").html(
        U.pause +
          `<div class="fsh-metric-strip">${values
            .map(
              ([k, v]) =>
                `<div class="fsh-metric"><div class="fsh-metric-label">${k}</div><div class="fsh-metric-value">${U.escape(v)}</div></div>`,
            )
            .join("")}</div><div class="fsh-dashboard-sections">${section(
            "统一收件箱",
            "ExternalConversation",
            conversations &&
              conversations.sort((a, b) =>
                (b.lastInboundAt || "").localeCompare(a.lastInboundAt || ""),
              ),
            (row) =>
              `<tr><td>${U.link("ExternalConversation", row.id, row.name)}</td><td>${U.badge(row.status)}</td><td>${U.badge(row.controlMode)}</td><td>${row.needsManualMatch ? '<span class="fsh-badge fsh-warning">身份待确认</span>' : "—"}</td><td>${U.escape(row.assignedUserName || "未分配")}</td></tr>`,
          )}${section(
            "需要审核的草稿",
            "AIReplyDraft",
            drafts && drafts.filter((d) => ["generated", "edited"].includes(d.status)),
            (row) =>
              `<tr><td>${U.link("AIReplyDraft", row.id, row.name)}</td><td>${U.link("ExternalConversation", row.conversationId, row.conversationName)}</td><td>${U.badge(row.riskLevel)}</td><td>${U.link("ExternalConversation", row.conversationId, "打开会话审核")}</td></tr>`,
          )}${section(
            "身份待确认",
            "ExternalIdentity",
            identities,
            (row) =>
              `<tr><td>${U.link("ExternalIdentity", row.id, row.displayName || row.name)}</td><td>${U.escape(U.status(row.channelType))}</td><td>${U.escape(row.externalUserId || "匿名访客")}</td><td>${U.badge(row.linkStatus)}</td></tr>`,
          )}${section(
            "失败或发送中的任务",
            "OutboundTask",
            exceptions &&
              exceptions.filter((t) => ["failed", "sending"].includes(t.status)),
            (row) =>
              `<tr><td>${U.link("OutboundTask", row.id, row.name)}</td><td>${U.link("ExternalConversation", row.conversationId, row.conversationName)}</td><td>${U.badge(row.status)}</td><td>${row.executionMode === "mock" ? U.badge("mock") : ""}</td><td title="${U.escape(row.errorMessage)}">${U.escape(row.errorMessage)}</td></tr>`,
          )}${section(
            "渠道状态",
            "ExternalChannel",
            channels,
            (row) =>
              `<tr><td>${U.link("ExternalChannel", row.id, row.name)}</td><td>${U.badge(row.connectionStatus)}</td></tr>`,
          )}${
            agents
              ? section(
                  "执行端状态",
                  "AutomationAgent",
                  agents &&
                    agents.map((a) => {
                      if (
                        a.status === "online" &&
                        (U.wait(a.lastHeartbeatAt) ?? 999) > 5
                      )
                        a.status = "heartbeatStale";
                      return a;
                    }),
                  (row) =>
                    `<tr><td>${U.link("AutomationAgent", row.id, row.name)}</td><td>${U.badge(row.status)}</td><td>${U.badge(row.mode)}</td><td>${U.escape(row.lastHeartbeatAt)}</td></tr>`,
                )
              : ""
          }</div>`,
      );
      U.localize(this);
      U.refreshOutboundNotice(this);
      this.$el.find(".fsh-refresh").prop("disabled", false);
    }
  };
});
