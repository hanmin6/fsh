define('custom:views/external-conversation/record/detail', ['views/record/detail', 'ajax', 'custom:views/fusanhe/common'], function (Dep, Ajax, U) {
    return class extends Dep {
        setup() { super.setup(); this.requestNumber=0; }
        afterRender() { super.afterRender(); this.renderWorkbench(); }
        async renderWorkbench() {
            const seq=++this.requestNumber;
            this.$el.find('.fsh-workspace-container').remove();
            this.$el.prepend('<section class="fsh-workspace-container"><div class="fsh-empty" role="status">正在加载询盘工作台…</div></section>');
            const where=[{type:'equals',attribute:'conversationId',value:this.model.id}];
            try {
                const [mr,dr,cr,tr]=await Promise.all([
                    Ajax.getRequest('ExternalMessage',{where,orderBy:'sentAt',order:'asc',maxSize:200}),
                    this.getAcl().checkScope('AIReplyDraft','read')?Ajax.getRequest('AIReplyDraft',{where,orderBy:'createdAt',order:'desc',maxSize:20}):Promise.resolve({list:[]}),
                    Ajax.getRequest('ExternalConversation',{orderBy:'lastMessageAt',order:'desc',maxSize:50}),
                    this.getAcl().checkScope('OutboundTask','read')?Ajax.getRequest('OutboundTask',{where,orderBy:'createdAt',order:'desc',maxSize:20}):Promise.resolve({list:[]})
                ]);
                if(seq!==this.requestNumber||!this.$el)return;
                this.drafts=dr.list||[];this.currentDraft=this.drafts[0];
                const messages=(mr.list||[]).map(m=>{
                    const attachments=Array.isArray(m.attachmentMetadata)?m.attachmentMetadata:(m.attachmentMetadata?.files||[]);
                    const task=tr.list.find(t=>t.platformMessageId===m.externalId);
                    return `<article class="fsh-message ${m.direction==='outbound'?'is-outbound':''}"><header class="fsh-message-meta"><strong>${U.escape(U.status(m.direction))} · ${U.escape(m.senderName)}</strong><time>${U.escape(m.sentAt)}</time></header><div class="fsh-message-body">${U.escape(m.body)}</div>${m.translatedBody?`<details open><summary>译文</summary><div class="fsh-message-body">${U.escape(m.translatedBody)}</div></details>`:''}${attachments.length?`<p>附件：${attachments.map(a=>U.escape(a.name||a.fileName||'附件')).join('、')}</p>`:''}${U.badge(m.deliveryStatus)}${task?.errorMessage?`<p class="fsh-danger">发送失败：${U.escape(task.errorMessage)}</p>`:''}</article>`;
                }).join('')||'<div class="fsh-empty">暂无消息。接收到询盘后，原文、译文和发送状态将在这里显示。</div>';
                const left=(cr.list||[]).map(c=>`<a class="fsh-conversation" aria-current="${c.id===this.model.id}" href="#ExternalConversation/view/${encodeURIComponent(c.id)}"><strong>${U.escape(c.contactName||c.leadName||c.name)}</strong><small>${U.escape(c.accountName)} · ${U.escape(c.channelName)} · ${U.escape(c.country)}</small><small title="${U.escape(c.lastMessagePreview)}">${U.escape(c.lastMessagePreview)}</small><small>${U.escape(U.status(c.status))} · 未读 ${c.unreadCount||0} · ${U.wait(c.lastInboundAt)??'—'} 分钟</small></a>`).join('');
                const c=this.model.attributes;
                const customer=U.link(c.contactId?'Contact':c.leadId?'Lead':'Account',c.contactId||c.leadId||c.accountId,c.contactName||c.leadName||c.accountName||'尚未匹配');
                const html=`<nav class="fsh-tabs" aria-label="会话分区"><button class="btn btn-default" data-pane="customers">会话</button><button class="btn btn-default" data-pane="messages">消息</button><button class="btn btn-default" data-pane="review">资料与审核</button></nav><section class="fsh-workbench" data-pane="messages"><aside class="fsh-pane fsh-pane-left"><h2>最近会话 <a href="#ExternalConversation" class="pull-right">全部</a></h2>${left||'<div class="fsh-empty">暂无其他询盘</div>'}</aside><main class="fsh-pane fsh-pane-messages"><h2>消息时间线 <small>${mr.total>=0?mr.total:(mr.list||[]).length} 条</small></h2>${messages}${mr.total>200?'<a href="#ExternalMessage">超过 200 条，打开外部消息查看完整历史</a>':''}${tr.list.filter(t=>t.status==='failed').map(t=>`<div class="fsh-notice fsh-danger">发送失败：${U.escape(t.errorMessage)} ${U.link('OutboundTask',t.id,'查看任务')}</div>`).join('')}</main><aside class="fsh-pane fsh-pane-right"><h2>客户信息</h2><dl class="fsh-kv"><dt>客户</dt><dd>${customer}</dd><dt>公司</dt><dd>${U.link('Account',c.accountId,c.accountName)}</dd><dt>渠道 / 国家</dt><dd>${U.escape(c.channelName)} / ${U.escape(c.country)}</dd><dt>负责人</dt><dd>${U.escape(c.assignedUserName||'未分配')}</dd><dt>当前状态</dt><dd>${U.badge(c.status)}</dd><dt>询盘产品</dt><dd>${U.escape(c.product)}</dd></dl><h3>AI 回复与审核</h3>${U.pause}<div class="fsh-actions"><button class="btn btn-default fsh-generate" ${!this.getAcl().checkScope('AIReplyDraft','create')?'disabled':''}>生成 AI 草稿</button></div><div class="fsh-draft-area"></div></aside></section>`;
                this.$el.find('.fsh-workspace-container').html(html);
                this.$el.find('.fsh-tabs button').on('click',e=>{this.$el.find('.fsh-workbench').attr('data-pane',e.currentTarget.dataset.pane);this.$el.find('.fsh-tabs button').attr('aria-pressed','false');$(e.currentTarget).attr('aria-pressed','true');});
                this.$el.find('.fsh-generate').on('click',()=>this.generateAiDraft());this.renderDraft();
            }catch(e){this.$el.find('.fsh-workspace-container').html('<div class="fsh-error" role="alert">询盘工作台加载失败，请确认消息读取权限后刷新。原生记录仍可在下方查看。</div>');}
        }
        renderDraft() {
            const d=this.currentDraft;
            if(!d){this.$el.find('.fsh-draft-area').html('<div class="fsh-empty">尚无 AI 草稿。请先阅读客户消息，再生成建议回复。</div>');return;}
            const editable=['generated','edited'].includes(d.status)&&this.getAcl().checkScope('AIReplyDraft','edit');
            const citations=(d.citedKnowledge||[]).map(k=>typeof k==='string'?U.escape(k):U.link('KnowledgeDocument',k.id||k.documentId,k.name||k.title||'引用资料')).join('<br>')||'无引用资料，请人工核实';
            const missing=(d.missingInformation||[]).map(x=>U.escape(typeof x==='string'?x:x.name||x.label||'待核实信息')).join('、')||'无';
            this.$el.find('.fsh-draft-area').html(`<div>${U.badge(d.status)} ${U.badge(d.riskLevel)} ${U.link('AIReplyDraft',d.id,'草稿记录')}</div><h3>AI 中文摘要</h3><p>${U.escape(d.summaryZh)}</p>${d.riskLevel==='high'?'<div class="fsh-notice fsh-danger">包含价格、MOQ、交期、认证、付款、折扣或承诺信息，需要人工确认。</div>':''}<h3>缺失信息</h3><p>${missing}</p><details><summary>引用知识</summary><p>${citations}</p></details><h3><label for="fsh-draft-text">英文回复草稿 · ${U.escape(d.suggestedLanguage||'语言未指定')}</label></h3><textarea id="fsh-draft-text" class="form-control fsh-draft-text" rows="10" ${editable?'':'readonly'}>${U.escape(d.draftText)}</textarea><div class="fsh-actions"><button class="btn btn-default fsh-save" ${editable?'':'disabled'}>保存修改</button><button class="btn btn-link fsh-reject" ${editable?'':'disabled'}>拒绝草稿</button></div><button class="btn btn-primary fsh-approve" ${['generated','edited'].includes(d.status)&&this.getAcl().checkScope('OutboundTask','create')?'':'disabled'}>批准并创建发送任务</button><div class="fsh-confirm-area"></div>`);
            this.$el.find('.fsh-save').on('click',()=>this.saveDraft(false));this.$el.find('.fsh-reject').on('click',()=>this.saveDraft(true));
            this.$el.find('.fsh-approve').on('click',()=>{
                this.$el.find('.fsh-confirm-area').html('<div class="fsh-notice"><p>请确认已核对回复内容、引用依据和商业承诺。此操作将批准草稿并创建发送任务。</p><label><input type="checkbox" class="fsh-confirm-check"> 我已完成人工审核</label><div class="fsh-actions"><button class="btn btn-primary fsh-confirm-submit" disabled>确认批准并创建任务</button><button class="btn btn-default fsh-cancel">取消</button></div></div>');
                this.$el.find('.fsh-confirm-check').on('change',e=>this.$el.find('.fsh-confirm-submit').prop('disabled',!e.currentTarget.checked));
                this.$el.find('.fsh-confirm-submit').on('click',()=>this.approveDraft(d.id));this.$el.find('.fsh-cancel').on('click',()=>this.$el.find('.fsh-confirm-area').empty());
            });
        }
        async runAction(fn,message) {
            if(this.busy)return;this.busy=true;this.$el.find('.fsh-pane-right button').prop('disabled',true);Espo.Ui.notify('正在处理…');
            try{await fn();Espo.Ui.success(message);await this.renderWorkbench();}catch(e){Espo.Ui.error('操作未完成，请检查权限和记录状态后重试。');this.renderDraft();this.$el.find('.fsh-generate').prop('disabled',!this.getAcl().checkScope('AIReplyDraft','create'));}finally{this.busy=false;}
        }
        generateAiDraft(){return this.runAction(()=>Ajax.postRequest(`Fusanhe/conversation/${this.model.id}/generate-draft`,{}),'AI 草稿已生成，请人工审核');}
        saveDraft(reject){const text=this.$el.find('.fsh-draft-text').val();if(!reject&&!text.trim()){Espo.Ui.error('回复内容不能为空');return;}return this.runAction(()=>Ajax.patchRequest(`AIReplyDraft/${this.currentDraft.id}`,reject?{status:'rejected'}:{draftText:text,status:'edited'}),reject?'草稿已拒绝':'修改已保存');}
        approveDraft(id){const draftText=this.$el.find('.fsh-draft-text').val();if(!draftText.trim()){Espo.Ui.error('回复内容不能为空');return;}return this.runAction(()=>Ajax.postRequest(`Fusanhe/draft/${id}/approve`,{draftText}),'已创建发送任务；全局停发开启，尚未向客户发送');}
    };
});
