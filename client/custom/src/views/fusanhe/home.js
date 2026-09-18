define("custom:views/fusanhe/home", [
  "views/main",
  "ajax",
  "custom:views/fusanhe/common",
], function (Dep, Ajax, U) {
  return class extends Dep {
    templateContent =
      '<div class="fsh-shell"><header class="fsh-header"><div><h1>外贸工作台</h1><div class="fsh-subtitle">广州福三和食品有限公司 · 询盘、回复与客户跟进</div></div><button class="btn btn-default fsh-refresh">刷新</button></header><div class="fsh-dashboard-body" aria-live="polite"></div></div>';
    updatePageTitle() {
      this.getHelper().pageTitle.setTitle(
        this.translate("外贸工作台", "labels", "Fusanhe"),
      );
    }
    afterRender() {
      super.afterRender();
      this.$el.find(".fsh-refresh").on("click", () => this.load());
      this.load();
    }
    async fetchAll(entity, select) {
      if (!this.getAcl().checkScope(entity, "read")) return null;
      const list = [];
      let offset = 0;
      while (true) {
        const r = await Ajax.getRequest(entity, {
          maxSize: 200,
          offset,
          select: select.join(","),
        });
        list.push(...r.list);
        if (r.list.length < 200 || (r.total >= 0 && list.length >= r.total))
          break;
        offset += 200;
      }
      return list;
    }
    async load() {
      if (this.busy) return;
      this.busy = true;
      this.$el.find(".fsh-refresh").prop("disabled", true);
      this.$el
        .find(".fsh-dashboard-body")
        .html('<div class="fsh-empty">正在加载运营数据…</div>');
      const specs = [
        [
          "ExternalConversation",
          [
            "id",
            "name",
            "createdAt",
            "status",
            "lastInboundAt",
            "lastMessageAt",
            "lastMessagePreview",
            "firstResponseMinutes",
            "assignedUserId",
            "assignedUserName",
            "channelName",
          ],
        ],
        [
          "AIReplyDraft",
          [
            "id",
            "name",
            "status",
            "wasEdited",
            "createdAt",
            "conversationId",
            "conversationName",
            "riskLevel",
            "summaryZh",
          ],
        ],
        [
          "OutboundTask",
          [
            "id",
            "name",
            "status",
            "errorMessage",
            "conversationName",
            "createdAt",
          ],
        ],
        ["Task", ["id", "name", "status", "dateEnd", "assignedUserId"]],
        ["ExternalChannel", ["id", "name", "type", "connectionStatus"]],
        [
          "AutomationAgent",
          ["id", "name", "status", "lastHeartbeatAt", "lastError"],
        ],
      ];
      const results = await Promise.allSettled(
        specs.map((s) => this.fetchAll(...s)),
      );
      const data = results.map((x) =>
        x.status === "fulfilled" ? x.value : null,
      );
      const [cs, ds, ts, todos, channels, agents] = data;
      if (agents)
        agents.forEach((a) => {
          if (a.status === "online" && (U.wait(a.lastHeartbeatAt) ?? 999) > 5)
            a.status = "heartbeatStale";
        });
      const today = new Date().toLocaleDateString();
      const count = (rows, fn) =>
        rows ? rows.filter(fn || (() => true)).length : "—";
      const rates = (rows, fn) =>
        rows && rows.length
          ? Math.round((rows.filter(fn).length / rows.length) * 100) + "%"
          : "—";
      const responded = (cs || []).filter(
        (c) => c.firstResponseMinutes != null,
      );
      const values = [
        [
          "今日新增询盘",
          count(
            cs,
            (c) =>
              new Date(
                c.createdAt.replace(" ", "T") + "Z",
              ).toLocaleDateString() === today,
          ),
        ],
        ["待回复", count(cs, (c) => ["new", "pending"].includes(c.status))],
        [
          "待审核",
          count(ds, (d) => ["generated", "edited"].includes(d.status)),
        ],
        [
          "超时未回复",
          count(
            cs,
            (c) =>
              ["new", "pending", "drafted", "waitingApproval"].includes(
                c.status,
              ) && U.wait(c.lastInboundAt) >= 120,
          ),
        ],
        ["未分配", count(cs, (c) => !c.assignedUserId)],
        ["AI 草稿", count(ds)],
        [
          "平均首次响应",
          responded.length
            ? (
                responded.reduce((n, c) => n + c.firstResponseMinutes, 0) /
                responded.length
              ).toFixed(1) + " 分钟"
            : "—",
        ],
        ["人工修改率", rates(ds, (d) => d.wasEdited || d.status === "edited")],
        ["发送成功率", rates(ts, (t) => t.status === "sent")],
        ["失败任务", count(ts, (t) => t.status === "failed")],
      ];
      const section = (title, entity, rows, columns) =>
        `<section class="fsh-section"><h2>${title}<a href="#${entity}">查看全部</a></h2>${
          rows === null
            ? '<div class="fsh-empty">暂不可用或没有读取权限。</div>'
            : !rows.length
              ? '<div class="fsh-empty">暂无记录。收到相关业务数据后将在这里显示。</div>'
              : `<div class="fsh-table-scroll"><table class="fsh-table"><tbody>${rows
                  .slice(0, 6)
                  .map(
                    (row) =>
                      `<tr><td>${U.link(entity, row.id, row.name)}</td>${columns.map((k) => `<td title="${U.escape(["status", "connectionStatus"].includes(k) ? U.status(row[k]) : row[k])}">${["status", "connectionStatus"].includes(k) ? U.badge(row[k]) : U.escape(row[k])}</td>`).join("")}</tr>`,
                  )
                  .join("")}</tbody></table></div>`
        }</section>`;
      this.$el
        .find(".fsh-dashboard-body")
        .html(
          U.pause +
            `<div class="fsh-metric-strip">${values.map(([k, v]) => `<div class="fsh-metric"><div class="fsh-metric-label">${k}</div><div class="fsh-metric-value">${U.escape(v)}</div></div>`).join("")}</div><p class="fsh-subtitle">今日按本地日期统计，其余指标为当前权限范围内的全部记录；比例无样本时显示 —。超时阈值 120 分钟。</p><div class="fsh-dashboard-sections">${section("最近询盘", "ExternalConversation", cs && cs.sort((a, b) => (b.lastMessageAt || "").localeCompare(a.lastMessageAt || "")), ["status", "lastMessageAt"])}${section("我的待办", "Task", todos && todos.filter((t) => t.assignedUserId === this.getUser().id && !["Completed", "Canceled"].includes(t.status)), ["status", "dateEnd"])}${section("需要审核的 AI 草稿", "AIReplyDraft", ds && ds.filter((d) => ["generated", "edited"].includes(d.status)), ["conversationName", "status"])}${section("失败或异常发送任务", "OutboundTask", ts && ts.filter((t) => t.status === "failed"), ["status", "errorMessage"])}${section("渠道状态", "ExternalChannel", channels, ["connectionStatus"])}${section("执行端状态", "AutomationAgent", agents, ["status", "lastHeartbeatAt"])}</div>`,
        );
      U.localize(this);
      this.busy = false;
      this.$el.find(".fsh-refresh").prop("disabled", false);
    }
  };
});
