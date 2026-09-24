define("custom:views/fusanhe/home", [
  "views/main",
  "ajax",
  "custom:views/fusanhe/common",
], function (Dep, Ajax, U) {
  // Dual-module entry point: CRM and AI customer service are sibling
  // workspaces sharing one login, one customer identity and one permission
  // model. Detailed metrics live inside each workspace.
  return class extends Dep {
    templateContent =
      '<div class="fsh-shell"><header class="fsh-header"><div><h1>福三和工作台</h1><div class="fsh-subtitle">广州福三和食品有限公司 · 请选择工作模块</div></div></header><div class="fsh-entry-body" aria-live="polite"></div></div>';
    updatePageTitle() {
      this.getHelper().pageTitle.setTitle(
        this.translate("选择工作模块", "labels", "Fusanhe"),
      );
    }
    afterRender() {
      super.afterRender();
      this.$el
        .find(".fsh-entry-body")
        .html('<div class="fsh-empty" role="status">正在加载模块入口…</div>');
      this.render();
    }
    async render() {
      const canCrm =
        this.getAcl().checkScope("Account", "read") ||
        this.getAcl().checkScope("Contact", "read") ||
        this.getAcl().checkScope("Lead", "read");
      const canService = this.getAcl().checkScope("ExternalConversation", "read");
      const crmCounts = await this.counts([
        ["Account", null],
        ["Contact", null],
        ["Lead", null],
        ["Task", { type: "equals", attribute: "assignedUserId", value: this.getUser().id }],
      ]);
      const serviceCounts = await this.counts([
        [
          "ExternalConversation",
          {
            type: "in",
            attribute: "status",
            value: ["new", "pending", "drafted", "waitingApproval"],
          },
        ],
        [
          "AIReplyDraft",
          { type: "in", attribute: "status", value: ["generated", "edited"] },
        ],
        this.getAcl().checkScope("ExternalIdentity", "read")
          ? [
              "ExternalIdentity",
              { type: "equals", attribute: "linkStatus", value: "unlinked" },
            ]
          : null,
        [
          "OutboundTask",
          { type: "in", attribute: "status", value: ["failed", "sending"] },
        ],
      ]);
      const entry = (href, title, desc, rows, allowed) =>
        allowed
          ? `<a class="fsh-entry" href="${href}"><h2>${title}</h2><p>${desc}</p><div class="fsh-entry-counts">${rows
              .map(([k, v]) => `${k}：<strong>${U.escape(v)}</strong>`)
              .join(" · ")}</div></a>`
          : "";
      this.$el.find(".fsh-entry-body").html(
        U.pause +
          (canService ? '<p class="fsh-notice"><a href="#Home/insights">历史客户与今日建议 →</a> · 查看导入覆盖率、AI 分析与人工跟进清单</p>' : "") +
          `<div class="fsh-entry-grid">${entry(
            "#Home/crm",
            "CRM 工作台",
            "客户、联系人、线索与跟进任务；商机请使用左侧导航原生入口。",
            [
              ["客户", crmCounts[0]],
              ["联系人", crmCounts[1]],
              ["线索", crmCounts[2]],
              ["我的待办", crmCounts[3]],
            ],
            canCrm,
          )}${entry(
            "#Home/service",
            "AI 客服工作台",
            "统一收件箱、草稿审核、身份确认与发送异常。",
            [
              ["进行中会话", serviceCounts[0]],
              ["待审核草稿", serviceCounts[1]],
              ["身份待确认", serviceCounts[2] === null ? "无权限" : serviceCounts[2]],
              ["发送异常", serviceCounts[3]],
            ],
            canService,
          )}</div>`,
      );
      U.localize(this);
      U.refreshOutboundNotice(this);
    }
    async counts(specs) {
      return Promise.all(
        specs.map(async (spec) => {
          if (!spec) return null;
          const [entity, where] = spec;
          if (!this.getAcl().checkScope(entity, "read")) return "无权限";
          try {
            const r = await Ajax.getRequest(entity, {
              maxSize: 1,
              where: where ? [where] : [],
            });
            return r.total >= 0 ? r.total : "—";
          } catch (e) {
            return "—";
          }
        }),
      );
    }
  };
});
