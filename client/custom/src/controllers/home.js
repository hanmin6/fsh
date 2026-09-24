define("custom:controllers/home", ["controllers/home"], function (Dep) {
  return class extends Dep {
    actionIndex() {
      this.main("custom:views/fusanhe/home");
    }
    actionInsights() {
      this.main("custom:views/fusanhe/insights");
    }
    actionCrm() {
      this.main("custom:views/fusanhe/crm-home");
    }
    actionService() {
      this.main("custom:views/fusanhe/service-home");
    }
  };
});
