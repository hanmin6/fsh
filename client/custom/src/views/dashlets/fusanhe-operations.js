define('custom:views/dashlets/fusanhe-operations', ['views/dashlets/abstract/base', 'ajax'], function (Dep, Ajax) {
    return class extends Dep {
        name = 'FusanheOperations';
        templateContent = '<div class="fsh-metrics"></div>';
        setup() {
            this.wait(Ajax.getRequest('Fusanhe/dashboard').then(data => { this.metrics = data; }));
        }
        afterRender() {
            const m = this.metrics || {};
            const values = [
                ['今日新增询盘', m.todayInquiries], ['待回复', m.waitingReply], ['待审核', m.waitingApproval],
                ['超时未回复', m.slaBreached], ['未分配', m.unassigned], ['AI 草稿', m.aiDrafts],
                ['平均首次响应', m.averageFirstResponseMinutes == null ? '—' : m.averageFirstResponseMinutes + ' 分钟'],
                ['人工修改率', Math.round((m.humanEditRate || 0) * 100) + '%'], ['发送成功率', Math.round((m.sendSuccessRate || 0) * 100) + '%'], ['失败任务', m.failedTasks]
            ];
            const html = `<style>.fsh-metric-strip{display:grid;grid-template-columns:repeat(5,minmax(110px,1fr));border-top:1px solid var(--border-color);border-left:1px solid var(--border-color)}.fsh-metric{padding:12px;border-right:1px solid var(--border-color);border-bottom:1px solid var(--border-color)}.fsh-metric-label{font-size:12px;color:var(--text-muted-color)}.fsh-metric-value{font-size:20px;font-weight:600;margin-top:3px;font-variant-numeric:tabular-nums}@media(max-width:900px){.fsh-metric-strip{grid-template-columns:repeat(2,1fr)}}</style><div class="fsh-metric-strip">${values.map(x => `<div class="fsh-metric"><div class="fsh-metric-label">${x[0]}</div><div class="fsh-metric-value">${x[1] == null ? 0 : x[1]}</div></div>`).join('')}</div>`;
            this.$el.find('.fsh-metrics').html(html);
        }
    };
});
