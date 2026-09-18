define('custom:views/fusanhe/context-detail',['views/record/detail','custom:views/fusanhe/common'],function(Dep,U){
 return class extends Dep {
  afterRender(){super.afterRender();this.$el.find('.fsh-detail-context').remove();const type=this.model.entityType;
   let text=type==='KnowledgeDocument'?'<div class="fsh-notice">AI 只能使用“已审核”且在有效期内的资料。草稿及已过期文档不可作为回复依据。</div>':type==='OutboundTask'?U.pause:U.pause+`<div class="fsh-notice">${U.link('ExternalConversation',this.model.get('conversationId'),'打开会话查看引用依据、编辑、批准或拒绝草稿')}${this.model.get('riskLevel')==='high'?'<p class="fsh-danger">包含价格、MOQ、交期、认证、付款、折扣或承诺信息，需要人工确认。</p>':''}</div>`;
   this.$el.prepend(`<div class="fsh-detail-context">${text}</div>`);
  }
 };
});
