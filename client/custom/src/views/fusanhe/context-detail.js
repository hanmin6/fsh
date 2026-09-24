define("custom:views/fusanhe/context-detail", [
  "views/record/detail",
  "custom:views/fusanhe/common",
  "custom:views/fusanhe/react-host",
], function (Dep, U, ReactHost) {
  return class extends Dep {
    unmountScreen = ReactHost.prototype.unmountScreen;
    getReactHost = ReactHost.prototype.getReactHost;
    mountScreen = ReactHost.prototype.mountScreen;

    async afterRender() {
      super.afterRender();
      this._contextDisposed = false;
      this.$el.find(".fsh-detail-context").remove();
      const panel = document.createElement("section");
      panel.className = "fsh-detail-context";
      panel.setAttribute("aria-label", this.translate("业务提醒", "labels", "Fusanhe"));
      panel.setAttribute("aria-busy", "true");
      this.$el.prepend(panel);
      const data = {
        type: this.model.entityType,
        conversationId: this.model.get("conversationId"),
        riskLevel: this.model.get("riskLevel"),
      };
      let mounted = false;
      try {
        mounted = await this.mountScreen("context-detail", data, panel);
      } catch {
        mounted = false;
      }
      if (this._contextDisposed || !panel.isConnected) return;
      panel.removeAttribute("aria-busy");
      if (mounted) return;
      const t = (value) => this.translate(value, "labels", "Fusanhe");
      if (data.type === "KnowledgeDocument") {
        panel.innerHTML = `<div class="fsh-notice">${U.escape(t("AI 只能使用“已审核”且在有效期内的资料。草稿及已过期文档不可作为回复依据。"))}</div>`;
      } else {
        panel.innerHTML = U.pause +
          (data.type !== "OutboundTask"
            ? `<div class="fsh-notice">${this.getAcl().checkScope("ExternalConversation", "read") ? U.link("ExternalConversation", data.conversationId, t("打开会话查看引用依据、编辑、批准或拒绝草稿")) : U.escape(t("没有读取权限"))}${data.riskLevel === "high" ? `<p class="fsh-danger">${U.escape(t("包含价格、MOQ、交期、认证、付款、折扣或承诺信息，需要人工确认。"))}</p>` : ""}</div>`
            : "");
        U.refreshOutboundNotice(this);
      }
    }

    remove(...args) {
      this._contextDisposed = true;
      this.unmountScreen();
      return super.remove(...args);
    }
  };
});
