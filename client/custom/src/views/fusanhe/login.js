define("custom:views/fusanhe/login", ["views/login"], function (Dep) {
  return class extends Dep {
    remove() {
      this.$el.removeClass("fsh-login");
      return super.remove();
    }
    afterRender() {
      super.afterRender();
      this.$el.addClass("fsh-login");
      const login = this.$el.find("#login");
      if (!login.length) return;
      const t = (label) => this.translate(label, "labels", "Fusanhe");
      this.$el.find(".fsh-login-photo").remove();
      login.find(".fsh-login-heading").remove();
      login.find(".logo").attr({
        src: "client/custom/res/fusanhe/logo-full.png",
        alt: "福三和 Fusanhe",
      });
      login
        .find(".panel-heading")
        .append(
          `<div class="fsh-login-heading"><h1>${t("广州福三和食品有限公司")}</h1><h2>${t("外贸客户与询盘工作台")}</h2></div>`,
        );
      login.before(
        '<div class="fsh-login-photo" aria-hidden="true"></div>',
      );
      this.$el.find("#btn-login").text(t("登录"));
    }
  };
});
