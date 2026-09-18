define('custom:views/fusanhe/list', ['views/main', 'ajax', 'custom:views/fusanhe/common'], function (Dep, Ajax, U) {
    const definitions = {
        ExternalConversation: {title:'统一询盘', columns:[['customer','客户 / 联系人'],['accountName','客户公司'],['channelName','渠道'],['country','国家'],['product','产品'],['lastMessagePreview','最后消息'],['unreadCount','未读'],['waiting','等待时间'],['assignedUserName','负责人'],['status','状态'],['lastMessageAt','最后消息时间']],sort:'lastMessageAt'},
        AIReplyDraft:{title:'AI 草稿审核队列',columns:[['customer','客户'],['accountName','公司'],['channelName','渠道'],['product','产品'],['summaryZh','原始问题摘要'],['suggestedLanguage','语言'],['riskLevel','风险'],['missingInformation','缺失信息'],['assignedUserName','负责人'],['createdAt','创建时间'],['waiting','等待时间'],['status','状态'],['review','审核']],sort:'createdAt'},
        KnowledgeDocument:{title:'知识文档',columns:[['name','文档名称'],['category','分类'],['product','产品'],['sourceType','文件类型'],['version','版本'],['approvalStatus','审核状态'],['effectiveFrom','生效日期'],['effectiveTo','失效日期'],['checksum','校验值'],['indexedAt','最后索引时间']],sort:'modifiedAt'},
        OutboundTask:{title:'发送任务',columns:[['conversationName','会话'],['customer','客户'],['channelName','渠道'],['status','状态'],['idempotencyKey','幂等键'],['claimedBy','执行端'],['retryCount','重试'],['createdAt','创建时间'],['completedAt','完成时间'],['platformMessageId','平台消息 ID'],['errorMessage','错误信息']],sort:'createdAt'},
        AutomationAgent:{title:'平台执行端',columns:[['name','执行端名称'],['status','状态'],['lastHeartbeatAt','最后心跳'],['capabilities','支持渠道'],['lastError','最近错误']],sort:'lastHeartbeatAt'}
    };
    return class extends Dep {
        templateContent = '<div class="fsh-shell"><div class="fsh-header"><div><h1 class="fsh-title"></h1><div class="fsh-subtitle">客户、询盘与后续行动</div></div><button class="btn btn-default" data-action="refresh">刷新</button></div><div class="fsh-list-notice"></div><form class="fsh-toolbar"></form><div class="fsh-list-body" aria-live="polite"></div><div class="fsh-pagination"></div></div>';
        setup() { super.setup(); this.entity = this.options.scope || this.scope || this.options.entityType; this.def = definitions[this.entity]; this.offset = 0; this.filters = {}; this.serial = 0; }
        afterRender() {
            super.afterRender();
            if (!this.def) return;
            this.$el.find('.fsh-title').text(this.def.title);
            this.$el.find('.fsh-list-notice').html(this.entity === 'OutboundTask' ? U.pause : this.entity === 'KnowledgeDocument' ? '<div class="fsh-notice">AI 只能使用“已审核”且在有效期内的资料。草稿及已过期文档不可作为回复依据。</div>' : '');
            const options = name => (this.getMetadata().get(['entityDefs',this.entity,'fields',name,'options']) || []).map(x=>`<option value="${U.escape(x)}">${U.escape(U.status(x))}</option>`).join('');
            let html = '<label>搜索<input class="form-control" type="search" name="text" placeholder="搜索名称或询盘内容"></label>';
            if (this.entity === 'ExternalConversation') html += '<label>渠道<select class="form-control" name="channelId"><option value="">全部渠道</option></select></label><label>负责人<select class="form-control" name="assignedUserId"><option value="">全部负责人</option><option value="unassigned">未分配</option></select></label><label>国家<input class="form-control" name="country" placeholder="国家 / 地区"></label>';
            const field = this.entity === 'KnowledgeDocument' ? 'approvalStatus':'status';
            html += `<label>状态<select class="form-control" name="${field}"><option value="">全部状态</option>${options(field)}</select></label>`;
            if (this.entity === 'ExternalConversation') html += '<label>未读<select class="form-control" name="unreadCount"><option value="">全部</option><option value="1">仅未读</option></select></label><label>SLA<select class="form-control" name="sla"><option value="">全部</option><option value="1">超过 120 分钟</option></select></label>';
            html += '<label>排序<select class="form-control" name="order"><option value="desc">最新在前</option><option value="asc">最早在前</option></select></label><button class="btn btn-default" type="submit">查询</button><button class="btn btn-link" type="button" data-action="clear">清除筛选</button>';
            this.$el.find('.fsh-toolbar').html(html).on('submit', e=>{e.preventDefault();this.offset=0;this.load();}).on('change','select',()=>{this.offset=0;this.load();});
            this.$el.find('[data-action=clear]').on('click',()=>{this.$el.find('form')[0].reset();this.offset=0;this.load();});
            this.$el.find('[data-action=refresh]').on('click',()=>this.load());
            this.$el.on('click.fsh','tr[data-id]',e=>{if($(e.target).closest('a,button').length)return;this.getRouter().navigate(`#${this.entity}/view/${e.currentTarget.dataset.id}`,{trigger:true});});
            this.$el.on('keydown.fsh','tr[data-id]',e=>{if(e.target!==e.currentTarget)return;if(e.key==='Enter'){e.preventDefault();this.getRouter().navigate(`#${this.entity}/view/${e.currentTarget.dataset.id}`,{trigger:true});}});
            if(this.entity === 'ExternalConversation') this.loadSelectors();
            this.load();
        }
        async loadSelectors() {
            for (const [entity,field] of [['ExternalChannel','channelId'],['User','assignedUserId']]) {
                if(!this.getAcl().checkScope(entity,'read'))continue;
                try {const r=await Ajax.getRequest(entity,{maxSize:200,orderBy:'name'}); const select=this.$el.find(`[name=${field}]`);(r.list||[]).forEach(x=>select.append($('<option>').val(x.id).text(x.name)));}catch(e){/* Existing ACL may restrict directory lookup. */}
            }
        }
        async load() {
            const seq=++this.serial; const values=Object.fromEntries(this.$el.find('form').serializeArray().map(x=>[x.name,x.value]));
            const where=[];
            for(const key of ['channelId','assignedUserId','country','status','approvalStatus']) if(values[key])where.push(values[key]==='unassigned'?{type:'isNull',attribute:key}:{type:'equals',attribute:key,value:values[key]});
            if(values.unreadCount)where.push({type:'greaterThan',attribute:'unreadCount',value:0});
            if(values.sla)where.push({type:'in',attribute:'status',value:['new','pending','drafted','waitingApproval']},{type:'before',attribute:'lastInboundAt',value:new Date(Date.now()-120*60000).toISOString().slice(0,19).replace('T',' ')});
            this.$el.find('.fsh-list-body').html('<div class="fsh-empty" role="status">正在加载…</div>');
            try {
                const result=await Ajax.getRequest(this.entity,{where,textFilter:values.text||'',orderBy:this.def.sort,order:values.order||'desc',offset:this.offset,maxSize:50});
                let rows=result.list||[];
                if(['AIReplyDraft','OutboundTask'].includes(this.entity)) {
                    const ids=[...new Set(rows.map(x=>x.conversationId).filter(Boolean))];
                    if(ids.length&&this.getAcl().checkScope('ExternalConversation','read')) {const r=await Ajax.getRequest('ExternalConversation',{where:[{type:'in',attribute:'id',value:ids}],maxSize:50});const by=Object.fromEntries(r.list.map(x=>[x.id,x])); rows=rows.map(x=>({...by[x.conversationId],...x,accountName:by[x.conversationId]?.accountName,contactName:by[x.conversationId]?.contactName,contactId:by[x.conversationId]?.contactId,leadId:by[x.conversationId]?.leadId,leadName:by[x.conversationId]?.leadName,accountId:by[x.conversationId]?.accountId,channelName:x.channelName||by[x.conversationId]?.channelName,product:by[x.conversationId]?.product}));}
                }
                if(this.entity==='ExternalConversation') {
                    const leads=[...new Set(rows.map(x=>x.leadId).filter(Boolean))];
                    if(leads.length&&this.getAcl().checkScope('Lead','read')){const lr=await Ajax.getRequest('Lead',{where:[{type:'in',attribute:'id',value:leads}],maxSize:50,select:'id,accountName'});const by=Object.fromEntries(lr.list.map(x=>[x.id,x]));rows=rows.map(x=>({...x,accountName:x.accountName||by[x.leadId]?.accountName}));}
                    if(this.getAcl().checkScope('ExternalMessage','read'))await Promise.all(rows.filter(x=>!x.lastMessagePreview).map(async x=>{const r=await Ajax.getRequest('ExternalMessage',{where:[{type:'equals',attribute:'conversationId',value:x.id}],orderBy:'sentAt',order:'desc',maxSize:1,select:'id,body'});x.lastMessagePreview=r.list[0]?.body;}));
                }
                if(seq!==this.serial)return;
                const body=rows.length?`<div class="fsh-table-scroll"><table class="fsh-table"><thead><tr>${this.def.columns.map(c=>`<th class="${['product','country','idempotencyKey','platformMessageId','checksum'].includes(c[0])?'fsh-secondary':''}">${c[1]}</th>`).join('')}</tr></thead><tbody>${rows.map(row=>`<tr tabindex="0" data-id="${U.escape(row.id)}" class="${row.unreadCount?'is-unread':''}">${this.def.columns.map(([field])=>this.cell(row,field)).join('')}</tr>`).join('')}</tbody></table></div>`:'<div class="fsh-empty">暂无符合条件的记录。可清除筛选或稍后刷新。</div>';
                this.$el.find('.fsh-list-body').html(body);
                this.$el.find('.fsh-pagination').html(`<span>${rows.length?this.offset+1:0}–${this.offset+rows.length} / ${result.total>=0?result.total:'更多'}</span><button class="btn btn-default fsh-prev" ${this.offset===0?'disabled':''}>上一页</button><button class="btn btn-default fsh-next" ${rows.length<50?'disabled':''}>下一页</button>`);
                this.$el.find('.fsh-prev').on('click',()=>{this.offset=Math.max(0,this.offset-50);this.load();});this.$el.find('.fsh-next').on('click',()=>{this.offset+=50;this.load();});
            } catch(e) {if(seq===this.serial)this.$el.find('.fsh-list-body').html('<div class="fsh-error" role="alert">无法加载记录，请检查访问权限或点击刷新重试。</div>');}
        }
        cell(row,field) {
            let value=row[field], html;
            if(field==='customer')html=U.link(row.contactId?'Contact':row.leadId?'Lead':'Account',row.contactId||row.leadId||row.accountId,row.contactName||row.leadName||row.accountName||row.name);
            else if(field==='name')html=U.link(this.entity,row.id,value);
            else if(field==='accountName')html=U.link('Account',row.accountId,value);
            else if(field==='conversationName')html=U.link('ExternalConversation',row.conversationId,value);
            else if(field==='review')html=U.link('ExternalConversation',row.conversationId,'打开会话审核');
            else if(['status','approvalStatus','riskLevel'].includes(field))html=U.badge(value);
            else if(field==='waiting'){const n=U.wait(this.entity==='ExternalConversation'?row.lastInboundAt:row.createdAt);const closed=['sent','closed','approved','rejected'].includes(row.status);value=closed?'—':n==null?'—':`${n} 分钟`;html=`<span class="${!closed&&n>=120?'fsh-danger':''}">${U.escape(value)}</span>`;}
            else if(Array.isArray(value)){value=value.map(x=>typeof x==='string'?U.status(x):x.name||x.title||'资料').join('、');html=U.escape(value);}
            else {html=U.escape(['checksum','idempotencyKey'].includes(field)&&value?value.slice(0,12)+'…':value);}
            return `<td class="${['product','country','idempotencyKey','platformMessageId','checksum'].includes(field)?'fsh-secondary':''}" title="${U.escape(['status','approvalStatus','riskLevel'].includes(field)?U.status(value):value)}">${html}</td>`;
        }
    };
});
