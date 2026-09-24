define("custom:views/dashlets/fusanhe-operations", ["views/dashlets/abstract/base"], function (Dep) {
  return class extends Dep {
    name = "FusanheOperations";
    templateContent = '<div class="fsh-notice"><a href="#Home/insights">历史客户与今日建议</a><p>查看真实同步覆盖率、客户会话、AI 分析依据与人工跟进建议。</p></div>';
  };
});
