define("custom:controllers/home", ["controllers/home"], function (Dep) {
  return class extends Dep {
    actionIndex() {
      this.main("custom:views/fusanhe/workspace");
    }
    actionWorkspace() {
      this.main("custom:views/fusanhe/workspace");
    }
    actionInsights() {
      this.main("custom:views/fusanhe/insights");
    }
    actionCrm() {
      this.main("custom:views/fusanhe/workspace");
    }
    actionService() {
      this.main("custom:views/fusanhe/service-home");
    }
  };
});
