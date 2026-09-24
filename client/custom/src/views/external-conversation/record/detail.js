define("custom:views/external-conversation/record/detail", [
  "views/record/detail",
  "ajax",
  "custom:views/fusanhe/common",
], function (Dep, Ajax, U) {
  return class extends Dep {
    setup() {
      super.setup();
      this.requestNumber = 0;
    }
    afterRender() {
      super.afterRender();
      this.renderWorkbench();
    }
    async renderWorkbench() {
      const seq = ++this.requestNumber;
      this.$el.find(".fsh-workspace-container").remove();
      this.$el.prepend(
        '<section class="fsh-workspace-container"><div class="fsh-empty" role="status">正在加载询盘工作台…</div></section>',
      );
      const where = [
        { type: "equals", attribute: "conversationId", value: this.model.id },
      ];
      try {
        const [mr, dr, cr, tr, identity] = await Promise.all([
          Ajax.getRequest("ExternalMessage", {
            where,
            orderBy: "sourceSequence",
            order: "asc",
            maxSize: 200,
          }),
          this.getAcl().checkScope("AIReplyDraft", "read")
            ? Ajax.getRequest("AIReplyDraft", {
                where,
                orderBy: "createdAt",
                order: "desc",
                maxSize: 20,
              })
            : Promise.resolve({ list: [] }),
          Ajax.getRequest("ExternalConversation", {
            orderBy: "lastMessageAt",
            order: "desc",
            maxSize: 50,
          }),
          this.getAcl().checkScope("OutboundTask", "read")
            ? Ajax.getRequest("OutboundTask", {
                where,
                orderBy: "createdAt",
                order: "desc",
                maxSize: 20,
              })
            : Promise.resolve({ list: [] }),
          this.model.get("identityId")
            ? Ajax.getRequest(
                "ExternalIdentity/" + this.model.get("identityId"),
              ).catch(() => null)
            : Promise.resolve(null),
        ]);
        const leadIds = [
          ...new Set(cr.list.map((c) => c.leadId).filter(Boolean)),
        ];
        if (leadIds.length && this.getAcl().checkScope("Lead", "read")) {
          const leads = await Ajax.getRequest("Lead", {
            where: [{ type: "in", attribute: "id", value: leadIds }],
            select: "id,accountName",
            maxSize: 50,
          });
          const byId = Object.fromEntries(leads.list.map((x) => [x.id, x]));
          cr.list.forEach((c) => {
            c.accountName = c.accountName || byId[c.leadId]?.accountName;
          });
        }
        const current = cr.list.find((c) => c.id === this.model.id);
        if (current && !current.lastMessagePreview && mr.list.length)
          current.lastMessagePreview = mr.list[mr.list.length - 1].body;
        if (seq !== this.requestNumber || !this.$el) return;
        this.drafts = dr.list || [];
        this.currentDraft = this.drafts[0];
        this.identity = identity;
        const messages =
          (mr.list || [])
            .map((m) => {
              const metadata = m.attachmentMetadata;
              const attachments = Array.isArray(metadata)
                ? metadata
                : Array.isArray(metadata?.items)
                  ? metadata.items
                  : Array.isArray(metadata?.files)
                    ? metadata.files
                    : [];
              const task = tr.list.find(
                (t) => t.platformMessageId === m.externalId,
              );
              const mockReceipt =
                m.direction === "outbound" && m.deliveryStatus === "mockSent"
                  ? '<p class="fsh-notice">模拟回执：演示环境回写结果，不代表真实客户已收到。</p>'
                  : "";
              const attachmentLabels = attachments.map((a) => {
                const name = U.escape(a.name || a.fileName || "附件");
                const details = [];
                if (typeof a.mediaType === "string" && a.mediaType.trim())
                  details.push(U.escape(a.mediaType));
                if (typeof a.size === "number" && Number.isFinite(a.size) && a.size >= 0) {
                  const units = ["B", "KB", "MB", "GB", "TB"];
                  let size = a.size;
                  let unit = 0;
                  while (size >= 1024 && unit < units.length - 1) {
                    size /= 1024;
                    unit += 1;
                  }
                  details.push(`${unit ? size.toFixed(1) : Math.round(size)} ${units[unit]}`);
                }
                return `${name}${details.length ? ` <small>(${details.join(" · ")})</small>` : ""}`;
              });
              return `<article class="fsh-message ${m.direction === "outbound" ? "is-outbound" : ""}"><header class="fsh-message-meta"><strong>${U.escape(U.status(m.direction))} · ${U.escape(m.senderName)}</strong><time>${U.escape(m.sentAt)}</time></header><div class="fsh-message-body">${U.escape(m.body)}</div>${m.translatedBody ? `<details open><summary>译文</summary><div class="fsh-message-body">${U.escape(m.translatedBody)}</div></details>` : ""}${attachmentLabels.length ? `<p>附件：${attachmentLabels.join("、")}</p>` : ""}${U.badge(m.deliveryStatus)}${mockReceipt}${task?.errorMessage ? `<p class="fsh-danger">发送失败：${U.escape(task.errorMessage)}</p>` : ""}</article>`;
            })
            .join("") ||
          '<div class="fsh-empty">暂无消息。接收到询盘后，原文、译文和发送状态将在这里显示。</div>';
        const left = (cr.list || [])
          .map(
            (c) =>
              `<a class="fsh-conversation" aria-current="${c.id === this.model.id}" href="#ExternalConversation/view/${encodeURIComponent(c.id)}"><strong>${U.escape(c.contactName || c.leadName || c.name)}</strong><small>${U.escape(c.accountName)} · ${U.escape(c.channelName)} · ${U.escape(c.country)}</small><small title="${U.escape(c.lastMessagePreview)}">${U.escape(c.lastMessagePreview)}</small><small>${U.escape(U.status(c.status))} · 未读 ${c.unreadCount || 0} · ${["sent", "replied", "closed"].includes(c.status) ? "已回复" : (U.wait(c.lastInboundAt) ?? "—") + " 分钟"}</small></a>`,
          )
          .join("");
        const c = {
          ...this.model.attributes,
          accountName: this.model.get("accountName") || current?.accountName,
        };
        const customer = U.link(
          c.contactId ? "Contact" : c.leadId ? "Lead" : "Account",
          c.contactId || c.leadId || c.accountId,
          c.contactName || c.leadName || c.accountName || "尚未匹配",
        );
        const canControl = this.getAcl().checkScope(
          "ExternalConversation",
          "edit",
        );
        const isHuman = c.controlMode === "human";
        const control = `<h2>接待控制</h2><p class="fsh-kv-inline"><span>接待状态：${U.badge(c.status)}</span><span>控制模式：${U.badge(c.controlMode || "aiAssist")}</span></p>${canControl ? `<div class="fsh-actions"><button class="btn btn-default fsh-control" data-mode="${isHuman ? "aiAssist" : "human"}">${isHuman ? "恢复 AI 辅助" : "人工接管"}</button></div><p class="fsh-subtitle">${isHuman ? "人工接管期间，未发送的自动任务不会被执行。" : "AI 辅助模式：草稿需人工批准后才会创建发送任务。"}</p>` : ""}`;
        const identityHtml = this.renderIdentityCard();
        const html = `<nav class="fsh-tabs" aria-label="会话分区"><button class="btn btn-default" data-pane="customers">会话</button><button class="btn btn-default" data-pane="messages">消息</button><button class="btn btn-default" data-pane="review">资料与审核</button></nav><section class="fsh-workbench" data-pane="messages"><aside class="fsh-pane fsh-pane-left"><h2>最近会话 <a href="#ExternalConversation" class="pull-right">全部</a></h2>${left || '<div class="fsh-empty">暂无其他询盘</div>'}</aside><main class="fsh-pane fsh-pane-messages"><h2>消息时间线 <small>${mr.total >= 0 ? mr.total : (mr.list || []).length} 条</small></h2>${messages}${mr.total > 200 ? '<a href="#ExternalMessage">超过 200 条，打开外部消息查看完整历史</a>' : ""}${tr.list
          .filter((t) => t.status === "failed")
          .map(
            (t) =>
              `<div class="fsh-notice fsh-danger">发送失败：${U.escape(t.errorMessage)} ${U.link("OutboundTask", t.id, "查看任务")}${t.executionMode === "mock" ? " " + U.badge("mock") : ""}</div>`,
          )
          .join(
            "",
          )}</main><aside class="fsh-pane fsh-pane-right">${control}${identityHtml}<h2>客户信息</h2><dl class="fsh-kv"><dt>客户</dt><dd>${customer}</dd><dt>公司</dt><dd>${U.link("Account", c.accountId, c.accountName)}</dd><dt>渠道 / 国家</dt><dd>${U.escape(c.channelName)} / ${U.escape(c.country)}</dd><dt>接待人</dt><dd>${U.escape(c.assignedUserName || "未分配")}</dd><dt>询盘产品</dt><dd>${U.escape(c.product)}</dd></dl><h2>转销售跟进</h2><div class="fsh-handoff-area"></div><h3>AI 回复与审核</h3>${U.pause}<div class="fsh-actions"><button class="btn btn-default fsh-generate" ${!this.getAcl().checkScope("AIReplyDraft", "create") ? "disabled" : ""}>生成 AI 草稿</button><button class="btn btn-default fsh-manual" ${!this.getAcl().checkScope("AIReplyDraft", "create") ? "disabled" : ""}>人工草稿</button></div><div class="fsh-manual-area"></div><div class="fsh-draft-area"></div></aside></section>`;
        this.$el.find(".fsh-workspace-container").html(html);
        this.$el.find(".fsh-tabs button").on("click", (e) => {
          this.$el
            .find(".fsh-workbench")
            .attr("data-pane", e.currentTarget.dataset.pane);
          this.$el.find(".fsh-tabs button").attr("aria-pressed", "false");
          $(e.currentTarget).attr("aria-pressed", "true");
        });
        this.$el
          .find(".fsh-generate")
          .on("click", () => this.generateAiDraft());
        this.$el.find(".fsh-manual").on("click", () => this.manualDraft());
        this.$el.find(".fsh-control").on("click", (e) =>
          this.setControlMode(e.currentTarget.dataset.mode),
        );
        this.bindIdentityCard();
        this.renderHandoff();
        this.renderDraft();
        U.localize(this);
        U.refreshOutboundNotice(this);
      } catch (e) {
        this.$el
          .find(".fsh-workspace-container")
          .html(
            '<div class="fsh-error" role="alert">询盘工作台加载失败，请确认消息读取权限后刷新。原生记录仍可在下方查看。</div>',
          );
      }
    }
    renderIdentityCard() {
      const c = this.model.attributes;
      if (!c.identityId)
        return '<h2>身份确认</h2><div class="fsh-empty">该会话尚未映射平台身份（历史数据）。新消息进入后将自动建立映射。</div>';
      const i = this.identity || {};
      const confirmed = i.linkStatus === "confirmed";
      const customerLine = confirmed
        ? U.link(
            i.accountId ? "Account" : i.contactId ? "Contact" : "Lead",
            i.accountId || i.contactId || i.leadId,
            i.accountName || i.contactName || i.leadName || "已关联客户",
          )
        : "未关联";
      return `<h2>身份确认</h2><dl class="fsh-kv"><dt>状态</dt><dd>${U.badge(i.linkStatus || "unlinked")}</dd><dt>关联客户</dt><dd>${customerLine}</dd><dt>平台身份</dt><dd>${U.escape(U.status(i.channelType))} · ${U.escape(i.externalUserId || "匿名访客（仅本会话）")}</dd>${i.emailAddress ? `<dt>邮箱</dt><dd>${U.escape(i.emailAddress)}</dd>` : ""}${i.phoneNumber ? `<dt>电话</dt><dd>${U.escape(i.phoneNumber)}</dd>` : ""}</dl>${
        confirmed
          ? ""
          : this.getAcl().checkScope("ExternalIdentity", "edit")
            ? '<div class="fsh-actions"><button class="btn btn-default fsh-id-find">查找匹配客户</button><button class="btn btn-default fsh-id-create">建立线索建档</button></div><p class="fsh-subtitle">公司名或姓名等弱匹配不会自动关联，需在此人工确认。</p><div class="fsh-idcand-area"></div>'
            : '<p class="fsh-subtitle">没有身份确认权限，请联系有权限的同事处理。</p>'
      }`;
    }
    bindIdentityCard() {
      this.$el.find(".fsh-id-find").on("click", () => this.findCandidates());
      this.$el
        .find(".fsh-id-create")
        .on("click", () => this.createCustomerFromIdentity());
    }
    async findCandidates() {
      const area = this.$el.find(".fsh-idcand-area");
      area.html('<div class="fsh-empty" role="status">正在查找…</div>');
      try {
        const r = await Ajax.getRequest(
          `Fusanhe/identity/${this.model.get("identityId")}/candidates`,
          { conversationId: this.model.id },
        );
        const list = r.candidates || [];
        if (!list.length) {
          area.html(
            '<div class="fsh-empty">未找到邮箱或电话精确匹配的客户。请先在 CRM 建档，再回到这里关联；或使用线索建档。</div>',
          );
          return;
        }
        area.html(
          list
            .map(
              (x) =>
                `<div class="fsh-idcand">${U.link(x.type, x.id, x.name)} <small>${U.escape(x.emailAddress || x.phoneNumber || "")}</small><button class="btn btn-primary btn-xs fsh-id-link" data-type="${U.escape(x.type)}" data-id="${U.escape(x.id)}" data-name="${U.escape(x.name)}">确认关联</button></div>`,
            )
            .join(""),
        );
        this.$el.find(".fsh-id-link").on("click", (e) => {
          const t = e.currentTarget.dataset;
          this.linkIdentity(t.type, t.id, t.name);
        });
      } catch (e) {
        area.html(
          '<div class="fsh-error" role="alert">候选查询失败：请确认会话读取权限后重试。</div>',
        );
      }
    }
    linkIdentity(targetType, targetId, name) {
      return this.runAction(
        () =>
          Ajax.postRequest(
            `Fusanhe/identity/${this.model.get("identityId")}/link`,
            {
              conversationId: this.model.id,
              targetType,
              targetId,
            },
          ),
        `已关联客户：${name}`,
      );
    }
    createCustomerFromIdentity() {
      return this.runAction(
        () =>
          Ajax.postRequest(
            `Fusanhe/identity/${this.model.get("identityId")}/create-customer`,
            { conversationId: this.model.id, targetType: "Lead" },
          ),
        "已建立线索并关联本会话",
      );
    }
    setControlMode(mode) {
      return this.runAction(
        () =>
          Ajax.postRequest(`Fusanhe/conversation/${this.model.id}/control`, {
            mode,
          }),
        mode === "human" ? "已人工接管，自动任务已暂停执行" : "已恢复 AI 辅助",
      );
    }
    manualDraft() {
      const area = this.$el.find(".fsh-manual-area");
      if (this.$el.find(".fsh-manual-text").length) return;
      area.prepend(
        `<div class="fsh-manual-form"><div class="fsh-form-row"><label for="fsh-manual-text">人工草稿内容</label><textarea id="fsh-manual-text" class="form-control fsh-manual-text" rows="6" placeholder="手动撰写回复，保存后走同一审核与发送任务流程"></textarea></div><div class="fsh-actions"><button class="btn btn-primary fsh-manual-save">创建人工草稿</button><button class="btn btn-link fsh-manual-cancel">取消</button></div></div>`,
      );
      this.$el.find(".fsh-manual-cancel").on("click", () => {
        this.$el.find(".fsh-manual-form").remove();
      });
      this.$el.find(".fsh-manual-save").on("click", async () => {
        const text = this.$el.find(".fsh-manual-text").val();
        if (!text.trim()) {
          Espo.Ui.error("草稿内容不能为空");
          return;
        }
        await this.runAction(
          () =>
            Ajax.postRequest(
              `Fusanhe/conversation/${this.model.id}/manual-draft`,
              { draftText: text },
            ),
          "人工草稿已创建，请审核",
        );
        this.$el.find(".fsh-manual-form").remove();
      });
    }
    renderHandoff() {
      const area = this.$el.find(".fsh-handoff-area");
      if (!area.length) return;
      const canHandoff =
        this.getAcl().checkScope("Task", "create") &&
        this.getAcl().checkScope("ExternalConversation", "read");
      if (!canHandoff) {
        area.html("<div class=\"fsh-empty\">没有创建跟进任务的权限。</div>");
        return;
      }
      area.html(
        '<button class="btn btn-default fsh-handoff-open">转销售跟进</button><div class="fsh-handoff-form-area"></div><div class="fsh-handoff-list" role="status">正在读取已创建任务…</div>',
      );
      this.$el
        .find(".fsh-handoff-open")
        .on("click", () => this.openHandoffForm());
      this.loadHandoffTasks();
    }
    async loadHandoffTasks() {
      const list = this.$el.find(".fsh-handoff-list");
      if (!list.length) return;
      try {
        const r = await Ajax.getRequest(
          `Fusanhe/conversation/${this.model.id}/handoff-tasks`,
        );
        list.html(
          r.tasks.length
            ? "已创建任务：" +
              r.tasks
                .map(
                  (t) =>
                    `${U.link("Task", t.id, t.name)}（${U.escape(U.status(t.status))} · ${U.escape(t.assignedUserName || "")} · ${U.escape(t.dateEnd || "")}）`,
                )
                .join("<br>")
            : "尚未创建跟进任务。",
        );
      } catch (e) {
        list.text("跟进任务读取失败，请稍后刷新。");
      }
    }
    async openHandoffForm() {
      const area = this.$el.find(".fsh-handoff-form-area");
      if (area.find(".fsh-handoff-form").length) return;
      area.html(
        `<div class="fsh-handoff-form"><div class="fsh-form-row"><label for="fsh-handoff-summary">需求摘要（必填）</label><textarea id="fsh-handoff-summary" class="form-control fsh-handoff-summary" rows="3" placeholder="客户需求、已确认信息与下一步建议"></textarea></div><div class="fsh-form-row"><label for="fsh-handoff-user">负责人</label><select id="fsh-handoff-user" class="form-control fsh-handoff-user"></select></div><div class="fsh-form-row"><label for="fsh-handoff-date">截止日期</label><input id="fsh-handoff-date" class="form-control fsh-handoff-date" type="date"></div><div class="fsh-actions"><button class="btn btn-primary fsh-handoff-submit">创建跟进任务</button><button class="btn btn-link fsh-handoff-cancel">取消</button></div><p class="fsh-subtitle">重复点击不会重复建任务；成功后可在任务中回到本会话。</p></div>`,
      );
      const date = area.find(".fsh-handoff-date");
      date.val(new Date(Date.now() + 3 * 86400000).toISOString().slice(0, 10));
      const select = area.find(".fsh-handoff-user");
      const owner = this.model.get("assignedUserId");
      let users = [];
      try {
        const r = await Ajax.getRequest("User", {
          maxSize: 100,
          orderBy: "name",
        });
        users = r.list || [];
      } catch (e) {
        /* Directory may be restricted; fall back to the current owner. */
      }
      const options = users.length
        ? users.map((u) => [u.id, u.name])
        : owner
          ? [[owner, this.model.get("assignedUserName") || "当前负责人"]]
          : [];
      select.html(
        options
          .map(
            ([id, name]) =>
              `<option value="${U.escape(id)}"${id === owner ? " selected" : ""}>${U.escape(name)}</option>`,
          )
          .join(""),
      );
      this.$el.find(".fsh-handoff-cancel").on("click", () => {
        area.empty();
      });
      this.$el.find(".fsh-handoff-submit").on("click", async () => {
        const summary = area.find(".fsh-handoff-summary").val();
        if (!summary.trim()) {
          Espo.Ui.error("请填写需求摘要");
          return;
        }
        await this.runAction(
          () =>
            Ajax.postRequest(`Fusanhe/conversation/${this.model.id}/handoff`, {
              summary,
              assignedUserId: select.val() || undefined,
              dateEnd: date.val() || undefined,
            }),
          "跟进任务已创建",
        );
        area.empty();
        this.loadHandoffTasks();
      });
    }
    renderDraft() {
      const d = this.currentDraft;
      if (!d) {
        this.$el
          .find(".fsh-draft-area")
          .html(
            '<div class="fsh-empty">尚无 AI 草稿。请先阅读客户消息，再生成建议回复或撰写人工草稿。</div>',
          );
        return;
      }
      const editable =
        ["generated", "edited"].includes(d.status) &&
        this.getAcl().checkScope("AIReplyDraft", "edit");
      const citations =
        (d.citedKnowledge || [])
          .map((k) => {
            if (typeof k === "string" && k.startsWith("cert:")) {
              return U.link(
                "FusanheCertificate",
                k.slice(5),
                "查看证书",
              );
            }
            return typeof k === "string"
              ? U.link("KnowledgeDocument", k, "查看引用资料")
              : U.link(
                  "KnowledgeDocument",
                  k.id || k.documentId,
                  k.name || k.title || "引用资料",
                );
          })
          .join("<br>") || "无引用资料，请人工核实";
      const missing =
        (d.missingInformation || [])
          .map((x) =>
            U.escape(
              typeof x === "string" ? x : x.name || x.label || "待核实信息",
            ),
          )
          .join("、") || "无";
      this.$el
        .find(".fsh-draft-area")
        .html(
          `<div>${U.badge(d.status)} ${U.badge(d.riskLevel)} ${U.link("AIReplyDraft", d.id, "草稿记录")}${d.modelProvider === "manual" ? " " + U.badge("human") : ""}</div><h3>AI 中文摘要</h3><p>${U.escape(d.summaryZh)}</p>${d.riskLevel === "high" ? '<div class="fsh-notice fsh-danger">包含价格、MOQ、交期、认证、付款、折扣或承诺信息，需要人工确认。</div>' : ""}<h3>缺失信息</h3><p>${missing}</p><details><summary>引用知识</summary><p>${citations}</p></details><h3><label for="fsh-draft-text">英文回复草稿 · ${U.escape({ en: "英语", zh: "中文", zh_CN: "简体中文" }[d.suggestedLanguage] || d.suggestedLanguage || "语言未指定")}</label></h3><textarea id="fsh-draft-text" class="form-control fsh-draft-text" rows="10" ${editable ? "" : "readonly"}>${U.escape(d.draftText)}</textarea><div class="fsh-actions"><button class="btn btn-default fsh-save" ${editable ? "" : "disabled"}>保存修改</button><button class="btn btn-link fsh-reject" ${editable ? "" : "disabled"}>拒绝草稿</button></div><button class="btn btn-primary fsh-approve" ${["generated", "edited"].includes(d.status) && this.getAcl().checkScope("OutboundTask", "create") ? "" : "disabled"}>批准并创建发送任务</button><div class="fsh-confirm-area"></div>`,
        );
      U.localize(this);
      this.$el.find(".fsh-save").on("click", () => this.saveDraft(false));
      this.$el.find(".fsh-reject").on("click", () => this.saveDraft(true));
      this.$el.find(".fsh-approve").on("click", () => {
        this.$el
          .find(".fsh-confirm-area")
          .html(
            '<div class="fsh-notice"><p>请确认已核对回复内容、引用依据和商业承诺。此操作将批准草稿并创建发送任务。</p><label><input type="checkbox" class="fsh-confirm-check"> 我已完成人工审核</label><div class="fsh-actions"><button class="btn btn-primary fsh-confirm-submit" disabled>确认批准并创建任务</button><button class="btn btn-default fsh-cancel">取消</button></div></div>',
          );
        U.localize(this);
        this.$el
          .find(".fsh-confirm-check")
          .on("change", (e) =>
            this.$el
              .find(".fsh-confirm-submit")
              .prop("disabled", !e.currentTarget.checked),
          );
        this.$el
          .find(".fsh-confirm-submit")
          .on("click", () => this.approveDraft(d.id));
        this.$el
          .find(".fsh-cancel")
          .on("click", () => this.$el.find(".fsh-confirm-area").empty());
      });
    }
    async runAction(fn, message) {
      if (this.busy) return;
      this.busy = true;
      this.$el.find(".fsh-pane-right button").prop("disabled", true);
      Espo.Ui.notify("正在处理…");
      let completed = false;
      try {
        await fn();
        completed = true;
        await this.model.fetch();
        Espo.Ui.success(message);
        await this.renderWorkbench();
      } catch (e) {
        Espo.Ui.error(
          completed
            ? "操作已完成，请刷新页面查看最新状态。"
            : "操作未完成，请检查权限和记录状态后重试。",
        );
        this.renderDraft();
        this.restoreActionButtons();
      } finally {
        this.busy = false;
      }
    }
    // After a failed action the buttons must come back, re-gated by
    // permission; otherwise one 4xx bricks the whole workbench pane.
    restoreActionButtons() {
      this.$el.find(".fsh-pane-right button").prop("disabled", false);
      const acl = this.getAcl();
      if (!acl.checkScope("AIReplyDraft", "create"))
        this.$el.find(".fsh-generate,.fsh-manual").prop("disabled", true);
      if (!(acl.checkScope("Task", "create") && acl.checkScope("ExternalConversation", "read")))
        this.$el.find(".fsh-handoff-open").prop("disabled", true);
      if (!acl.checkScope("ExternalIdentity", "edit"))
        this.$el.find(".fsh-id-find,.fsh-id-create").prop("disabled", true);
    }
    generateAiDraft() {
      return this.runAction(
        () =>
          Ajax.postRequest(
            `Fusanhe/conversation/${this.model.id}/generate-draft`,
            {},
          ),
        "AI 草稿已生成，请人工审核",
      );
    }
    saveDraft(reject) {
      const text = this.$el.find(".fsh-draft-text").val();
      if (!reject && !text.trim()) {
        Espo.Ui.error("回复内容不能为空");
        return;
      }
      return this.runAction(
        () =>
          Ajax.patchRequest(
            `AIReplyDraft/${this.currentDraft.id}`,
            reject
              ? { status: "rejected" }
              : { draftText: text, status: "edited" },
          ),
        reject ? "草稿已拒绝" : "修改已保存",
      );
    }
    approveDraft(id) {
      const draftText = this.$el.find(".fsh-draft-text").val();
      if (!draftText.trim()) {
        Espo.Ui.error("回复内容不能为空");
        return;
      }
      const state = U.outboundState();
      const suffix =
        state === true
          ? "；全局停发开启，尚未向客户发送"
          : state === false
            ? "；全局停发已关闭，任务可被执行端领取"
            : "";
      return this.runAction(
        () => Ajax.postRequest(`Fusanhe/draft/${id}/approve`, { draftText }),
        "已创建发送任务" + suffix,
      );
    }
  };
});
