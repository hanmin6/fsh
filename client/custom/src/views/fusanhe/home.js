define("custom:views/fusanhe/home", [
  "views/main", "ajax", "custom:views/fusanhe/common",
], function (Dep, Ajax, U) {
  return class extends Dep {
    templateContent = '<div class="fsh-shell fsh-home"><header class="fsh-header"><div><h1>福三和工作台</h1><div class="fsh-subtitle">客户跟进与订单进展</div></div><button class="btn btn-default fsh-refresh" type="button">刷新</button></header><div class="fsh-home-body" aria-live="polite"></div></div>';

    updatePageTitle() { this.getHelper().pageTitle.setTitle("福三和工作台"); }
    afterRender() {
      super.afterRender();
      this.$el.find(".fsh-refresh").on("click", () => this.load());
      this.load();
    }
    // Orders are optional. Respect the configured navigation and scope ACL.
    ordersEnabled() {
      const contains = (items) => items.some(item => item === "FusanheSalesOrder" ||
        (item && typeof item === "object" && contains(item.itemList || [])));
      return contains(this.getConfig().get("tabList") || []);
    }
    period(now = new Date()) {
      // Business reporting uses Asia/Shanghai, regardless of browser timezone.
      const day = new Date(now.getTime() + 8 * 3600000);
      day.setUTCHours(0, 0, 0, 0);
      const monday = new Date(day);
      monday.setUTCDate(day.getUTCDate() - (day.getUTCDay() + 6) % 7);
      const stamp = date => new Date(date.getTime() - 8 * 3600000).toISOString().slice(0, 19).replace("T", " ");
      return { today: stamp(day), week: stamp(monday), end: now.toISOString().slice(0, 19).replace("T", " "), label: day.toISOString().slice(0, 10), weekLabel: monday.toISOString().slice(0, 10) };
    }
    async counts(specs) {
      return Promise.all(specs.map(async spec => {
        if (!spec) return "未启用";
        const [entity, where] = spec;
        if (!this.getAcl().checkScope(entity, "read")) return "无权限";
        try {
          const r = await Ajax.getRequest(entity, { maxSize: 1, where: where ? [where] : [] });
          return r.total >= 0 ? r.total : "暂不可用";
        } catch (e) { return "加载失败"; }
      }));
    }
    async orders(enabled) {
      if (!enabled) return { message: "销售订单功能尚未启用。启用后显示已确认和已完成订单的客户、负责人及交期。" };
      if (!this.getAcl().checkScope("FusanheSalesOrder", "read")) return { message: "没有销售订单读取权限。" };
      try {
        return await Ajax.getRequest("FusanheSalesOrder", {
          maxSize: 8, orderBy: "modifiedAt", order: "desc",
          select: "id,name,number,accountId,accountName,status,assignedUserName,customerRequiredDate,internalConfirmedDate",
          where: [{ type: "in", attribute: "status", value: ["confirmed", "completed"] }],
        });
      } catch (e) { return { message: "订单加载失败，请点击页面右上方“刷新”重试。" }; }
    }
    renderOrders(result) {
      if (result.message) return `<p class="fsh-empty">${U.escape(result.message)}</p>`;
      if (!result.list?.length) return '<p class="fsh-empty">暂无已确认或已完成订单。订单确认后会在这里显示。</p>';
      return `<div class="fsh-home-table" role="region" aria-label="已购客户订单" tabindex="0"><table class="fsh-table"><thead><tr><th scope="col">客户 / 订单</th><th scope="col">订单状态</th><th scope="col">负责人</th><th scope="col">客户要求交期</th><th scope="col">内部确认交期</th><th scope="col">操作</th></tr></thead><tbody>${result.list.map(row => `<tr><td>${this.getAcl().checkScope("Account", "read") ? U.link("Account", row.accountId, row.accountName) : U.escape(row.accountName)}<small>${U.escape(row.number || row.name)}</small></td><td>${U.badge(row.status)}</td><td>${U.escape(row.assignedUserName || "未分配")}</td><td>${U.escape(row.customerRequiredDate || "未记录")}</td><td>${U.escape(row.internalConfirmedDate || "待确认")}</td><td>${U.link("FusanheSalesOrder", row.id, "查看订单")}</td></tr>`).join("")}</tbody></table></div>`;
    }
    metrics(labels, values) {
      return `<dl class="fsh-home-metrics">${labels.map((label, i) => `<div><dt>${label}</dt><dd${typeof values[i] === "number" ? "" : ' class="fsh-metric-unavailable"'}>${U.escape(values[i])}</dd></div>`).join("")}</dl>`;
    }
    async load() {
      if (this.loading) return;
      this.loading = true;
      this.$el.find(".fsh-refresh").prop("disabled", true);
      const body = this.$el.find(".fsh-home-body");
      body.attr("aria-busy", "true");
      if (!this.loaded) body.html('<p class="fsh-empty" role="status">正在加载客户与订单数据…</p>');
      try {
        const p = this.period(), enabled = this.ordersEnabled();
        const created = start => ({ type: "and", value: [
          { type: "greaterThanOrEquals", attribute: "createdAt", value: start },
          { type: "lessThanOrEquals", attribute: "createdAt", value: p.end },
        ] });
        const [values, orders] = await Promise.all([
          this.counts([
            ["Account", created(p.today)], ["Lead", created(p.today)],
            ["Task", { type: "and", value: [
              { type: "equals", attribute: "assignedUserId", value: this.getUser().id },
              { type: "notIn", attribute: "status", value: ["Completed", "Canceled"] },
              { type: "lessThanOrEquals", attribute: "dateEnd", value: p.end },
            ] }],
            ["Account", created(p.week)], ["Lead", created(p.week)],
            enabled ? ["FusanheSalesOrder", created(p.week)] : null,
          ]), this.orders(enabled),
        ]);
        body.html(`<section class="fsh-home-section" aria-labelledby="fsh-today"><div class="fsh-section-heading"><h2 id="fsh-today">今日客户概览</h2><span>${p.label} · 北京时间</span></div>${this.metrics(["今日新增客户", "今日新增线索", "我的到期未完成任务"], values.slice(0, 3))}</section><section class="fsh-home-section" aria-labelledby="fsh-orders"><div class="fsh-section-heading"><h2 id="fsh-orders">已购客户流程跟踪</h2>${enabled && this.getAcl().checkScope("FusanheSalesOrder", "read") ? '<a href="#FusanheSalesOrder">查看全部订单</a>' : ""}</div><p class="fsh-section-caption">按最近更新展示最多 8 笔已确认或已完成订单；同一客户可有多笔订单。</p>${this.renderOrders(orders)}</section><section class="fsh-home-section" aria-labelledby="fsh-week"><div class="fsh-section-heading"><h2 id="fsh-week">本周小结</h2><span>${p.weekLabel} 至今 · 北京时间</span></div>${this.metrics(["本周新增客户", "本周新增线索", "本周新建订单（含草稿）"], values.slice(3))}<p class="fsh-section-caption">统计范围为当前账号可读取的记录；到期任务包含逾期任务。</p></section>`);
        this.loaded = true;
      } catch (e) {
        body.html('<p class="fsh-error" role="alert">工作台加载失败，请点击“刷新”重试。</p>');
      } finally {
        this.loading = false;
        body.attr("aria-busy", "false");
        this.$el.find(".fsh-refresh").prop("disabled", false);
      }
    }
  };
});
