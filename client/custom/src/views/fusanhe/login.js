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
        .append('<div class="fsh-login-heading"><h1></h1><h2></h2></div>');
      login.find(".fsh-login-heading h1").text(t("广州福三和食品有限公司"));
      login.find(".fsh-login-heading h2").text(t("外贸客户与询盘工作台"));
      login.before(
        '<div class="fsh-login-photo" aria-hidden="true"></div>',
      );
      // Espo renders this as a role=button anchor without a tabindex.
      // Keep its existing click handler and make keyboard activation possible.
      login
        .find('[data-action="toggleShowPassword"]')
        .attr("tabindex", "0")
        .off("keydown.fsh-login")
        .on("keydown.fsh-login", (event) => {
          if (event.key !== "Enter" && event.key !== " ") return;
          event.preventDefault();
          event.currentTarget.click();
        });
      this.$el.find("#btn-login").text(t("登录"));
    }
  };
});
