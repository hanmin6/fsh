define('custom:views/external-conversation/record/detail', ['views/record/detail', 'ajax'], function (Dep, Ajax) {
    return class extends Dep {
        setup() {
            super.setup();
            this.addMenuItem('buttons', {
                name: 'generateAiDraft',
                label: 'Generate AI Draft',
                style: 'primary',
                onClick: () => this.generateAiDraft()
            });
        }

        afterRender() {
            super.afterRender();
            this.renderWorkbench();
        }

        async renderWorkbench() {
            const where = [{type: 'equals', attribute: 'conversationId', value: this.model.id}];
            const [messageResult, draftResult] = await Promise.all([
                Ajax.getRequest('ExternalMessage', {where, orderBy: 'sentAt', order: 'asc', maxSize: 50}),
                Ajax.getRequest('AIReplyDraft', {where, orderBy: 'createdAt', order: 'desc', maxSize: 10})
            ]);
            const messages = messageResult.list || [];
            const drafts = draftResult.list || [];
            const currentDraft = drafts[0];
            const escape = value => $('<div>').text(value || '').html();
            const timeline = messages.map(item => `
                <article class="fsh-message ${item.direction === 'outbound' ? 'is-outbound' : 'is-inbound'}">
                    <div class="fsh-message-meta"><strong>${escape(item.senderName || item.direction)}</strong><time>${escape(item.sentAt)}</time></div>
                    <div class="fsh-message-body">${escape(item.body).replace(/\n/g, '<br>')}</div>
                    <div class="fsh-message-state">${escape(item.deliveryStatus)}</div>
                </article>`).join('') || '<div class="fsh-empty">暂无消息</div>';
            const draft = currentDraft ? `
                <div class="fsh-ai-state"><span>${escape(currentDraft.status)}</span><span>风险：${escape(currentDraft.riskLevel)}</span></div>
                <div class="fsh-summary">${escape(currentDraft.summaryZh)}</div>
                <textarea class="form-control fsh-draft-text" rows="12">${escape(currentDraft.draftText)}</textarea>
                <div class="fsh-actions">
                    <button class="btn btn-primary fsh-approve" data-id="${escape(currentDraft.id)}" ${currentDraft.status === 'approved' || currentDraft.status === 'sent' ? 'disabled' : ''}>批准并创建发送任务</button>
                </div>` : '<div class="fsh-empty">尚未生成 AI 回复草稿</div>';
            const customerId = this.model.get('contactId') || this.model.get('leadId') || this.model.get('accountId');
            const customerType = this.model.get('contactId') ? 'Contact' : (this.model.get('leadId') ? 'Lead' : 'Account');
            const customerLink = customerId ? `<a href="#${customerType}/view/${customerId}">打开客户资料</a>` : '尚未匹配客户';
            const html = `<style>
                .fsh-workbench{display:grid;grid-template-columns:minmax(190px,24%) minmax(360px,1fr) minmax(280px,34%);border:1px solid var(--border-color);border-radius:8px;margin-bottom:16px;min-height:480px;background:var(--panel-bg)}
                .fsh-pane{min-width:0;padding:16px;overflow:auto}.fsh-pane+.fsh-pane{border-left:1px solid var(--border-color)}
                .fsh-pane h4{font-size:13px;font-weight:600;margin:0 0 12px}.fsh-kv{display:grid;grid-template-columns:72px 1fr;gap:8px;font-size:13px;margin:8px 0}.fsh-kv span{color:var(--text-muted-color)}
                .fsh-message{max-width:88%;border:1px solid var(--border-color);border-radius:6px;padding:10px 12px;margin:0 0 10px}.fsh-message.is-outbound{margin-left:auto;background:var(--state-success-bg)}
                .fsh-message-meta{display:flex;justify-content:space-between;gap:8px;font-size:12px}.fsh-message-meta time,.fsh-message-state{color:var(--text-muted-color);font-size:11px}.fsh-message-body{font-size:13px;line-height:1.55;margin:6px 0}.fsh-ai-state{display:flex;gap:8px;margin-bottom:10px;font-size:12px}.fsh-ai-state span{border:1px solid var(--border-color);border-radius:4px;padding:3px 6px}.fsh-summary{font-size:13px;margin-bottom:10px}.fsh-draft-text{font-size:13px;line-height:1.55}.fsh-actions{margin-top:10px;display:flex;justify-content:flex-end}.fsh-empty{color:var(--text-muted-color);font-size:13px;padding:24px 0}@media(max-width:1100px){.fsh-workbench{grid-template-columns:220px 1fr}.fsh-pane-right{grid-column:1/-1;border-left:0!important;border-top:1px solid var(--border-color)}}
            </style><section class="fsh-workbench">
                <aside class="fsh-pane"><h4>客户与询盘</h4><div class="fsh-kv"><span>客户</span><strong>${customerLink}</strong><span>渠道</span><strong>${escape(this.model.get('channelName'))}</strong><span>国家</span><strong>${escape(this.model.get('country'))}</strong><span>产品</span><strong>${escape(this.model.get('product'))}</strong><span>负责人</span><strong>${escape(this.model.get('assignedUserName') || '未分配')}</strong><span>状态</span><strong>${escape(this.model.get('status'))}</strong></div></aside>
                <main class="fsh-pane"><h4>消息时间线</h4>${timeline}</main>
                <aside class="fsh-pane fsh-pane-right"><h4>AI 回复与审核</h4>${draft}</aside>
            </section>`;
            this.$el.find('.fsh-workbench').remove();
            this.$el.prepend(html);
            this.$el.find('.fsh-approve').on('click', event => this.approveDraft(event.currentTarget.dataset.id));
        }

        async generateAiDraft() {
            Espo.Ui.notify('正在生成 AI 回复草稿…');
            try {
                await Ajax.postRequest(`Fusanhe/conversation/${this.model.id}/generate-draft`, {});
                Espo.Ui.success('AI 回复草稿已生成');
                await this.model.fetch();
                await this.renderWorkbench();
            } catch (e) {
                Espo.Ui.error('生成失败，请查看服务端日志');
                throw e;
            }
        }

        async approveDraft(id) {
            const draftText = this.$el.find('.fsh-draft-text').val();
            await Ajax.postRequest(`Fusanhe/draft/${id}/approve`, {draftText});
            Espo.Ui.success('已批准并创建发送任务');
            await this.model.fetch();
            await this.renderWorkbench();
        }
    };
});
