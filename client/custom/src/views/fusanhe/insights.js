define('custom:views/fusanhe/insights', ['custom:views/fusanhe/react-host', 'ajax', 'custom:views/fusanhe/common'], function (Dep, Ajax, U) {
  const states = {pending: '未分析', completed: '已完成', failed: '分析失败', stale: '待重新分析'};
  const e = value => U.escape(value == null ? '—' : String(value));
  const time = value => {
    if (!value) return '—';
    const date = new Date(value.replace(' ', 'T') + 'Z');
    return Number.isNaN(date.getTime()) ? '时间待确认' : date.toLocaleString('zh-CN', {timeZone: 'Asia/Shanghai', hour12: false});
  };
  const link = (type, id, text) => `<a href="#${type}/view/${encodeURIComponent(id)}">${e(text)}</a>`;
  return class extends Dep {
    templateContent = `<div class="fsh-ui-mount" aria-busy="true">正在读取同步与分析状态…</div><div class="fsh-legacy" hidden><div class="fsh-shell fsh-insights">
      <header class="fsh-header"><div><h1>历史客户与今日建议</h1><div class="fsh-subtitle">Alibaba · 按会话核对 · 上海时间</div></div><a href="#Home">返回工作台</a></header>
      <div class="fsh-insights-notice" role="status"></div><div class="fsh-insights-metrics" aria-live="polite">正在读取同步与分析状态…</div>
      <section class="fsh-insights-section"><h2>今日建议 <small class="fsh-insights-day"></small></h2><div class="fsh-insights-suggestions"></div></section>
      <section class="fsh-insights-section"><h2>历史客户会话</h2><form class="fsh-insights-toolbar"><label>搜索 <input class="form-control input-sm" name="q" placeholder="客户会话名称 / 平台 ID" maxlength="100"></label><label>状态 <select class="form-control input-sm" name="status"><option value="">全部</option><option value="pending">未分析</option><option value="completed">已分析</option><option value="failed">分析失败</option><option value="stale">待重新分析</option><option value="unmatched">身份待确认</option></select></label><button class="btn btn-default btn-sm" type="submit">查询 / 刷新</button></form>
      <div class="fsh-insights-list" aria-live="polite">正在加载…</div><div class="fsh-insights-paging"><button class="btn btn-default btn-sm" data-action="previous">上一页</button><span></span><button class="btn btn-default btn-sm" data-action="next">下一页</button></div></section>
      <section class="fsh-insights-detail fsh-insights-section" aria-live="polite"><h2>客户分析</h2><p>选择会话的“查看分析”，核对画像与原始依据。</p></section></div></div>`;
    events = {
      'submit .fsh-insights-toolbar': function (ev) { ev.preventDefault(); this.offset = 0; this.loadInsights(); },
      'click [data-action="previous"]': function () { this.offset = Math.max(0, this.offset - 25); this.loadInsights(); },
      'click [data-action="next"]': function () { this.offset += 25; this.loadInsights(); },
      'click [data-insight-id]': function (ev) { this.loadDetail(ev.currentTarget.dataset.insightId); },
    };
    setup() { super.setup(); this.offset = 0; this.requestVersion = 0; this.detailVersion = 0; }
    updatePageTitle() { this.getHelper().pageTitle.setTitle('历史客户与今日建议'); }
    async afterRender() {
      super.afterRender();
      this._insightsDisposed = false;
      let mounted = false;
      try { mounted = await this.mountScreen('insights', {}, this.$el.find('.fsh-ui-mount')[0]); }
      catch { mounted = false; }
      if (this._insightsDisposed) return;
      if (mounted) { this.$el.find('.fsh-ui-mount').removeAttr('aria-busy'); return; }
      this.$el.find('.fsh-ui-mount').hide();
      this.$el.find('.fsh-legacy').removeAttr('hidden');
      this.loadInsights();
    }
    remove(...args) {
      this._insightsDisposed = true;
      this.requestVersion++;
      this.detailVersion++;
      return super.remove(...args);
    }
    async loadInsights() {
      const version = ++this.requestVersion;
      this.$el.find('.fsh-insights-paging button').prop('disabled', true);
      this.$el.find('.fsh-insights-list').attr('aria-busy', 'true');
      try {
        const d = await Ajax.getRequest('Fusanhe/insights', {q: this.$el.find('[name=q]').val() || '', status: this.$el.find('[name=status]').val() || '', offset: this.offset, limit: 25});
        if (version !== this.requestVersion) return;
        const c = d.coverage;
        this.$el.find('.fsh-insights-notice').text(d.outboundPaused === true ? '全局停发已开启 · 本页只提供建议，下一步由人工执行。' : d.outboundPaused === false ? '注意：全局停发未开启。演示前请由管理员检查；本页不会发送消息。' : '外发状态未知。本页不会发送消息；请先核查发送开关。');
        const metrics = [['平台可见会话', c.platformVisible ?? '待核对'], ['已导入会话', c.imported], ['同步失败', c.failedSync ?? '未知'], ['身份待确认', c.pendingIdentity], ['分析完成', c.analysisCompleted], ['分析失败', c.analysisFailed], ['分析已过期', c.analysisStale]];
        this.$el.find('.fsh-insights-metrics').html(`<div class="fsh-insights-strip">${metrics.map(([k,v]) => `<div><span>${e(k)}</span><strong>${e(v)}</strong></div>`).join('')}</div><p>${e(c.reason)} ${d.scope === 'own' ? '当前仅显示本人负责的会话。' : ''}</p><p>最后同步：${e(time(c.lastSyncAt))} · 最后分析：${e(time(c.lastAnalysisAt))}</p>`);
        this.$el.find('.fsh-insights-day').text(`${d.date} · 共 ${d.suggestionTotal} 条${d.suggestionTotal > 50 ? '，显示优先 50 条' : ''}`);
        this.$el.find('.fsh-insights-suggestions').html(d.suggestions.length ? `<div class="table-responsive"><table class="table table-striped"><thead><tr><th>优先级</th><th>客户会话 / 依据</th><th>原因与建议动作</th><th>负责人</th></tr></thead><tbody>${d.suggestions.map(s => `<tr><td>P${e(s.priority)}</td><td>${link('ExternalConversation', s.id, s.name)}</td><td><strong>${e(s.reason)}</strong><br>${e(s.action)}</td><td>${e(s.owner)}</td></tr>`).join('')}</tbody></table></div>` : '<p class="fsh-empty">暂无建议。导入真实会话后，系统按身份与跟进状态生成建议。</p>');
        this.$el.find('.fsh-insights-list').html(d.list.length ? `<div class="table-responsive"><table class="table table-striped"><thead><tr><th>客户会话</th><th>平台 ID</th><th>身份</th><th>负责人</th><th>最近消息</th><th>AI 分析</th></tr></thead><tbody>${d.list.map(r => `<tr><td>${link('ExternalConversation', r.id, r.name)}${r.customer ? '<br>' + link(r.customer.type, r.customer.id, '打开 CRM 客户') : ''}</td><td>${e(r.externalId)}</td><td>${r.needsManualMatch ? '待确认' : '已关联'}</td><td>${e(r.owner)}</td><td>${e(time(r.lastMessageAt))}</td><td>${e(states[r.analysisStatus] || r.analysisStatus)} <button type="button" class="btn btn-link btn-sm" data-insight-id="${e(r.id)}">查看分析</button></td></tr>`).join('')}</tbody></table></div>` : '<p class="fsh-empty">没有符合条件的历史会话。未同步的数据与模拟记录不会计入这里。</p>');
        this.$el.find('.fsh-insights-paging span').text(`第 ${Math.floor(this.offset / 25) + 1} 页 · ${d.total} 条会话`);
        this.$el.find('[data-action=previous]').prop('disabled', this.offset === 0);
        this.$el.find('[data-action=next]').prop('disabled', this.offset + d.list.length >= d.total);
      } catch (error) {
        if (version !== this.requestVersion) return;
        this.$el.find('.fsh-insights-list').html('<p class="text-danger" role="alert">读取失败或没有访问权限。请使用“查询 / 刷新”重试。</p>');
        this.$el.find('.fsh-insights-notice').text('数据未能刷新，请勿依据旧统计进行对账。');
      } finally { if (version === this.requestVersion) this.$el.find('.fsh-insights-list').attr('aria-busy', 'false'); }
    }
    async loadDetail(id) {
      const version = ++this.detailVersion;
      const panel = this.$el.find('.fsh-insights-detail');
      panel.html('<h2>客户分析</h2><p>正在读取…</p>');
      try {
        const d = await Ajax.getRequest('Fusanhe/insights/' + encodeURIComponent(id));
        if (version !== this.detailVersion) return;
        const a = d.analysis;
        const fields = [['中文摘要', 'summaryZh'], ['需求', 'demand'], ['产品', 'products'], ['历史进展', 'historyProgress'], ['最新状态', 'latestStatus'], ['购买话题信号（待确认）', 'buyingSignals'], ['风险', 'risks'], ['缺失信息', 'missingFacts'], ['下一步', 'nextAction']];
        panel.html(`<h2>${e(d.name)} · ${e(states[d.analysisStatus] || d.analysisStatus)}</h2><p>${e(d.analysisNotice)}${d.analysisError ? ' 错误代码：' + e(d.analysisError) : ''}</p>${d.analysisStatus === 'stale' ? '<p class="text-warning">来源已有变化，下方为旧分析，请等待重新分析。</p>' : ''}${a ? `<dl>${fields.map(([label,key]) => `<div><dt>${e(label)}</dt><dd>${e(Array.isArray(a[key]) ? a[key].join('；') || '待确认' : a[key] || '待确认')}</dd></div>`).join('')}</dl><p>模型：${e(d.model)} · 生成时间：${e(time(d.analysisAt))} · ${e(d.promptVersion)}</p><p>分析依据：${d.evidence.map(m => link('ExternalMessage', m.id, time(m.sentAt) + ' ' + (m.direction === 'inbound' ? '客户消息' : '我方消息'))).join(' · ')}</p>` : ''}<p>${link('ExternalConversation', id, '打开原始会话与消息记录')}</p>`);
      } catch (error) { if (version === this.detailVersion) panel.html('<h2>客户分析</h2><p class="text-danger">分析读取失败或无权限，请重新选择会话。</p>'); }
    }
  };
});
