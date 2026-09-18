define("custom:views/dashlets/fusanhe-operations", [
  "views/dashlets/abstract/base",
], function (Dep) {
  return class extends Dep {
    name = "FusanheOperations";
    templateContent =
      '<div class="fsh-notice">外贸运营工作台已整合询盘、审核与发送状态。<a href="#Home">打开工作台</a></div>';
  };
});
