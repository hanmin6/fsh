define("custom:controllers/home", ["controllers/home"], function (Dep) {
  return class extends Dep {
    openWorkspace(page, tab = "") {
      const q = new URLSearchParams(location.search);
      q.set("workspace", page);
      if (tab) q.set("tab", tab); else q.delete("tab");
      q.delete("record"); q.delete("entity");
      history.replaceState(null, "", location.pathname + "?" + q + "#Home/workspace");
      this.main("custom:views/fusanhe/workspace");
    }
    actionIndex() {
      this.main("custom:views/fusanhe/workspace");
    }
    actionWorkspace() {
      this.main("custom:views/fusanhe/workspace");
    }
    actionInsights() {
      this.openWorkspace("customers", "insights");
    }
    actionCrm() {
      this.main("custom:views/fusanhe/workspace");
    }
    actionService() {
      this.openWorkspace("messages");
    }
  };
});
