define("custom:views/fusanhe/customer-detail", [
  "views/record/detail",
  "ajax",
  "custom:views/fusanhe/common",
  "custom:views/fusanhe/react-host",
], function (Dep, Ajax, U, ReactHost) {
  return class extends Dep {
    unmountScreen = ReactHost.prototype.unmountScreen;
    getReactHost = ReactHost.prototype.getReactHost;
    mountScreen = ReactHost.prototype.mountScreen;

    async afterRender() {
      super.afterRender();
      this._customerDisposed = false;
      this.$el.find(".fsh-customer-context").remove();
      const panel = document.createElement("section");
      panel.className = "fsh-customer-context";
      panel.setAttribute("aria-label", this.translate("客户业务概览", "labels", "Fusanhe"));
      panel.setAttribute("aria-busy", "true");
      this.$el.prepend(panel);
      const type = this.model.entityType;
      const data = { type, id: this.model.id, attributes: { ...this.model.attributes } };
      let mounted = false;
      try {
        mounted = await this.mountScreen("customer-detail", data, panel);
      } catch {
        mounted = false;
      }
      if (this._customerDisposed || !panel.isConnected) return;
      panel.removeAttribute("aria-busy");
      if (!mounted) this.loadLegacyCustomerContext(panel, data);
    }

    remove(...args) {
      this._customerDisposed = true;
      this.unmountScreen();
      return super.remove(...args);
    }

    async loadLegacyCustomerContext(panel, { type, id, attributes: m }) {
      panel.textContent = this.translate("正在读取客户跟进信息…", "labels", "Fusanhe");
      const field = type === "Account" ? "accountId" : type === "Contact" ? "contactId" : "leadId";
      try {
        const [conversations, tasks] = await Promise.all([
          this.getAcl().checkScope("ExternalConversation", "read")
            ? Ajax.getRequest("ExternalConversation", {
                where: [{ type: "equals", attribute: field, value: id }],
                orderBy: "lastMessageAt", order: "desc", maxSize: 20,
              })
            : Promise.resolve({ list: [] }),
          this.getAcl().checkScope("Task", "read")
            ? Ajax.getRequest("Task", {
                where: [
                  { type: "equals", attribute: "parentId", value: id },
                  { type: "equals", attribute: "parentType", value: type },
                  { type: "notIn", attribute: "status", value: ["Completed", "Canceled"] },
                ],
                orderBy: "dateEnd", order: "asc", maxSize: 5,
              })
            : Promise.resolve({ list: [] }),
        ]);
        if (this._customerDisposed || !panel.isConnected) return;
        const list = conversations.list || [];
        const latest = list[0] || {};
        const t = (label) => this.translate(label, "labels", "Fusanhe");
        const row = (label, value) => `<dt>${U.escape(t(label))}</dt><dd>${value || U.escape(t("未记录"))}</dd>`;
        panel.innerHTML = `<h2>${U.escape(t("客户业务概览"))}</h2><dl class="fsh-kv">${row("客户 / 公司", U.escape(m.accountName || m.name))}${row("国家 / 地区", U.escape(m.billingAddressCountry || m.addressCountry || latest.country))}${row("主要联系人", U.escape(latest.contactName || (type !== "Account" ? m.name : "")))}${row("邮箱", U.escape(m.emailAddress))}${row("客户负责人", U.escape(m.assignedUserName || t("未分配")))}${row("来源渠道", U.escape(latest.channelName || m.source))}${row("感兴趣产品", U.escape([...new Set(list.map((item) => item.product).filter(Boolean))].join("、")))}${row("最近联系", U.escape(latest.lastMessageAt))}${row("客户阶段", U.escape(U.status(m.status)))}${row("下一步", (tasks.list || []).map((task) => `${U.link("Task", task.id, task.name)} · ${U.escape(task.dateEnd)}`).join("<br>"))}</dl><h3>${U.escape(t("最近询盘"))}</h3>${list.length ? list.slice(0, 5).map((item) => `<div>${U.link("ExternalConversation", item.id, item.name)} · ${U.badge(item.status)}</div>`).join("") : U.escape(t("暂无关联询盘"))}`;
      } catch {
        if (!this._customerDisposed && panel.isConnected)
          panel.textContent = this.translate("客户业务概览暂不可用，请检查读取权限后刷新。", "labels", "Fusanhe");
      }
    }
  };
});
