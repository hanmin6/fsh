define("custom:views/dashlets/fusanhe-operations", ["views/dashlets/abstract/base"], function (Dep) {
  return class extends Dep {
    name = "FusanheOperations";
    templateContent = '<div class="fsh-operations-dashlet"><a class="fsh-operations-link" href="#Home/insights"></a><p class="fsh-operations-description"></p></div>';

    afterRender() {
      super.afterRender();
      this.$el.find(".fsh-operations-link").text(this.translate("历史客户与今日建议", "labels", "Fusanhe"));
      this.$el.find(".fsh-operations-description").text(this.translate("查看真实同步覆盖率、客户会话、AI 分析依据与人工跟进建议。", "labels", "Fusanhe"));
    }
  };
});
