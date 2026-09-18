define("custom:views/fusanhe/customer-detail", [
  "views/record/detail",
  "ajax",
  "custom:views/fusanhe/common",
], function (Dep, Ajax, U) {
  return class extends Dep {
    afterRender() {
      super.afterRender();
      this.loadCustomerContext();
    }
    async loadCustomerContext() {
      this.$el.find(".fsh-customer-context").remove();
      this.$el.prepend(
        '<section class="fsh-customer-context fsh-notice" aria-live="polite">正在读取客户跟进信息…</section>',
      );
      const type = this.model.entityType,
        field =
          type === "Account"
            ? "accountId"
            : type === "Contact"
              ? "contactId"
              : "leadId";
      try {
        const r = this.getAcl().checkScope("ExternalConversation", "read")
          ? await Ajax.getRequest("ExternalConversation", {
              where: [
                { type: "equals", attribute: field, value: this.model.id },
              ],
              orderBy: "lastMessageAt",
              order: "desc",
              maxSize: 20,
            })
          : { list: [] };
        const tasks = this.getAcl().checkScope("Task", "read")
          ? await Ajax.getRequest("Task", {
              where: [
                { type: "equals", attribute: "parentId", value: this.model.id },
                { type: "equals", attribute: "parentType", value: type },
                {
                  type: "notIn",
                  attribute: "status",
                  value: ["Completed", "Canceled"],
                },
              ],
              orderBy: "dateEnd",
              order: "asc",
              maxSize: 5,
            })
          : { list: [] };
        const c = r.list[0] || {},
          m = this.model.attributes;
        const identities =
          r.list
            .filter((x) => x.externalUserId)
            .map(
              (x) =>
                `${U.escape(x.channelName)}：${U.escape(x.externalUserId)}`,
            )
            .join("；") || "未记录平台身份";
        this.$el.find(".fsh-customer-context").html(
          `<h2>客户业务概览</h2><dl class="fsh-kv"><dt>客户 / 公司</dt><dd>${U.escape(m.accountName || m.name)}</dd><dt>国家 / 地区</dt><dd>${U.escape(m.billingAddressCountry || m.addressCountry || c.country || "未记录")}</dd><dt>主要联系人</dt><dd>${U.escape(c.contactName || (type !== "Account" ? m.name : "未记录"))}</dd><dt>邮箱</dt><dd>${U.escape(m.emailAddress || "未记录")}</dd><dt>负责人</dt><dd>${U.escape(m.assignedUserName || c.assignedUserName || "未分配")}</dd><dt>来源渠道</dt><dd>${U.escape(c.channelName || m.source || "未记录")}</dd><dt>感兴趣产品</dt><dd>${U.escape([...new Set(r.list.map((x) => x.product).filter(Boolean))].join("、") || "未记录")}</dd><dt>最近联系</dt><dd>${U.escape(c.lastMessageAt || "暂无询盘消息")}</dd><dt>最近回复</dt><dd>${U.escape(c.lastOutboundAt || "暂无发出回复记录")}</dd><dt>平台身份</dt><dd>${identities}</dd><dt>WhatsApp</dt><dd>未单独记录，请在联系人信息中核实</dd><dt>客户阶段</dt><dd>${U.escape(U.status(m.status) || "请查看关联商机")}</dd><dt>下一步</dt><dd>${tasks.list.map((t) => U.link("Task", t.id, t.name) + " · " + U.escape(t.dateEnd)).join("<br>") || "暂无关联待办，请创建跟进任务"}</dd><dt>风险</dt><dd>${r.list.some((x) => x.needsManualMatch) ? "客户匹配待人工确认" : "查看下方备注及会话草稿风险"}</dd></dl><h3>最近询盘</h3>${
            r.list.length
              ? r.list
                  .slice(0, 5)
                  .map(
                    (x) =>
                      `<div>${U.link("ExternalConversation", x.id, x.name)} · ${U.badge(x.status)} · ${U.escape(x.lastMessageAt)}</div>`,
                  )
                  .join("")
              : "暂无关联询盘"
          }`,
        );
        U.localize(this);
      } catch (e) {
        this.$el
          .find(".fsh-customer-context")
          .text("客户业务概览暂不可用，请检查读取权限后刷新。");
      }
    }
  };
});
