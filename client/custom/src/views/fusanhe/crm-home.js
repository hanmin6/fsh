define("custom:views/fusanhe/crm-home", [
  "views/main",
  "ajax",
  "custom:views/fusanhe/common",
], function (Dep, Ajax, U) {
  // CRM workspace: customers, contacts, leads and follow-up tasks.
  // Opportunities keep their native navigation entry.
  return class extends Dep {
    templateContent =
      '<div class="fsh-shell"><header class="fsh-header"><div><h1>CRM 工作台</h1><div class="fsh-subtitle">客户、联系人、线索与跟进任务</div></div><button class="btn btn-default fsh-refresh">刷新</button></header><div class="fsh-dashboard-body" aria-live="polite"></div></div>';
    updatePageTitle() {
      this.getHelper().pageTitle.setTitle(
        this.translate("CRM 工作台", "labels", "Fusanhe"),
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
        .html('<div class="fsh-empty" role="status">正在加载客户数据…</div>');
      const [tAcc, tCon, tLead, tTodo] = await Promise.all([
        this.total("Account"),
        this.total("Contact"),
        this.total("Lead"),
        this.total("Task", {
          type: "equals",
          attribute: "assignedUserId",
          value: this.getUser().id,
        }),
      ]);
      const [accounts, contacts, leads, todos] = await Promise.all([
        this.recent("Account", ["id", "name", "assignedUserName", "createdAt"]),
        this.recent("Contact", ["id", "name", "accountName", "createdAt"]),
        this.recent("Lead", ["id", "name", "accountName", "status", "createdAt"]),
        this.recent(
          "Task",
          ["id", "name", "status", "dateEnd", "parentType", "parentId"],
          {
            where: {
              type: "equals",
              attribute: "assignedUserId",
              value: this.getUser().id,
            },
          },
        ),
      ]);
      const values = [
        ["客户公司", tAcc ?? "—"],
        ["联系人", tCon ?? "—"],
        ["线索", tLead ?? "—"],
        ["我的待办", tTodo ?? "—"],
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
            "最近客户",
            "Account",
            accounts,
            (row) =>
              `<tr><td>${U.link("Account", row.id, row.name)}</td><td>${U.escape(row.assignedUserName || "未分配")}</td><td>${U.escape(row.createdAt)}</td></tr>`,
          )}${section(
            "最近联系人",
            "Contact",
            contacts,
            (row) =>
              `<tr><td>${U.link("Contact", row.id, row.name)}</td><td>${U.link("Account", row.accountId, row.accountName)}</td><td>${U.escape(row.createdAt)}</td></tr>`,
          )}${section(
            "最近线索",
            "Lead",
            leads,
            (row) =>
              `<tr><td>${U.link("Lead", row.id, row.name)}</td><td>${U.escape(row.accountName)}</td><td>${U.badge(row.status)}</td></tr>`,
          )}${section(
            "我的待办",
            "Task",
            todos &&
              todos.filter((t) => !["Completed", "Canceled"].includes(t.status)),
            (row) =>
              `<tr><td>${U.link("Task", row.id, row.name)}</td><td>${U.badge(row.status)}</td><td>${U.escape(row.dateEnd)}</td>${
                row.parentType === "ExternalConversation" && row.parentId
                  ? `<td>${U.link("ExternalConversation", row.parentId, "来源会话")}</td>`
                  : "<td>—</td>"
              }</tr>`,
          )}</div>`,
      );
      U.localize(this);
      this.$el.find(".fsh-refresh").prop("disabled", false);
    }
  };
});
