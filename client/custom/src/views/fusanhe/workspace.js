define('custom:views/fusanhe/workspace', ['views/main', 'ajax'], function (Dep, Ajax) {
  let loading;
  let salesLoading;
  function salesAssets(stamp) {
    if (!document.getElementById('fusanhe-sales-css')) {
      const link = document.createElement('link'); link.id = 'fusanhe-sales-css'; link.rel = 'stylesheet';
      link.href = 'client/custom/res/sales/style.css?v=' + encodeURIComponent(stamp); document.head.appendChild(link);
    }
    if (window.FusanheSales) return Promise.resolve();
    if (!salesLoading) salesLoading = new Promise((resolve, reject) => {
      const script = document.createElement('script'); script.src = 'client/custom/res/sales/sales.js?v=' + encodeURIComponent(stamp);
      script.onload = resolve; script.onerror = () => {salesLoading = null; script.remove(); reject(new Error('跟进模块加载失败'));}; document.head.appendChild(script);
    });
    return salesLoading;
  }
  function assets(stamp) {
    if (!document.getElementById('fusanhe-workspace-css')) {
      const link = document.createElement('link');
      link.id = 'fusanhe-workspace-css'; link.rel = 'stylesheet';
      link.href = 'client/custom/res/workspace/workspace.css?v=' + encodeURIComponent(stamp);
      document.head.appendChild(link);
    }
    if (window.FusanheWorkspace) return Promise.resolve();
    if (!loading) loading = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = 'client/custom/res/workspace/workspace.js?v=' + encodeURIComponent(stamp);
      script.onload = resolve;
      script.onerror = () => { loading = null; script.remove(); reject(new Error('加载失败')); };
      document.head.appendChild(script);
    });
    return loading;
  }
  return class extends Dep {
    templateContent = '<div class="fusanhe-workspace-root"><p role="status">正在打开福三和工作台…</p></div>';
    updatePageTitle() { this.getHelper().pageTitle.setTitle('福三和工作台'); }
    afterRender() {
      super.afterRender();
      const element = this.el.querySelector('.fusanhe-workspace-root');
      const stamp = this.getConfig().get('appTimestamp') || '1';
      const isSales = new URLSearchParams(location.search).get('workspace') === 'sales';
      (isSales ? salesAssets(stamp) : assets(stamp).then(() => salesAssets(stamp).catch(() => {}))).then(() => {
        if (!element.isConnected) return;
        this.disposeWorkspace?.();
        document.body.classList.add('fusanhe-workspace-active');
        const host = {
          get: (path, params) => Ajax.getRequest(path, params),
          post: (path, data) => Ajax.postRequest(path, data),
          patch: (path, data) => Ajax.patchRequest(path, data),
          can: (entity, action = 'read') => this.getAcl().checkScope(entity, action),
          native: (entity, id, action) => this.getRouter().navigate(entity + (id ? '/' + (action || 'view') + '/' + id : action ? '/' + action : ''), {trigger: true}),
          user: {id: this.getUser().id, name: this.getUser().get('name') || '共享工作台'},
        };
        this.disposeWorkspace = (isSales ? window.FusanheSales : window.FusanheWorkspace).mount(element, host);
        if (!isSales) this.disposeSalesNavigation = window.FusanheSales?.decorate(element);
      }).catch(error => { console.error('Workspace mount', error); element.textContent = '工作台加载失败，请刷新页面重试。'; });
    }
    remove() { document.body.classList.remove('fusanhe-workspace-active'); this.disposeSalesNavigation?.(); this.disposeWorkspace?.(); this.disposeWorkspace = null; return super.remove(); }
  };
});
