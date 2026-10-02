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
      login.find(".logo").attr({
        src: "client/custom/res/fusanhe/logo-full.png",
        alt: "福三和 Fusanhe",
      });
      login.find(".fsh-login-heading").remove();
      login
        .find(".panel-heading")
        .append(
          '<div class="fsh-login-heading"><h1>广州福三和食品有限公司</h1><p>Guangzhou Fusanhe Food Co., Ltd.</p><h2>外贸客户与询盘工作台</h2></div>',
        );
      // Keep the native form and handlers intact; only group its presentation.
      this.$el.find(".fsh-login-photo").remove();
      if (!login.parent().hasClass("fsh-login-layout")) {
        login.wrap('<div class="fsh-login-layout"></div>');
      }
      login.before(
        '<div class="fsh-login-photo" role="img" aria-label="福三和广州工厂"></div>',
      );
      const userName = login.find('input[name="username"], input[name="userName"], #field-userName');
      const password = login.find('input[name="password"], #field-password');
      userName.attr({placeholder: "账号", "aria-label": "账号", autocomplete: "username"});
      password.attr({placeholder: "密码", "aria-label": "密码", autocomplete: "current-password"});
      login.find('label[for="field-userName"], label[for="username"], label[for="userName"]').text("账号");
      login.find('label[for="field-password"], label[for="password"]').text("密码");
      login.find('[data-action="toggleShowPassword"]')
        .attr({title: "显示或隐藏密码", "aria-label": "显示或隐藏密码", tabindex: "0"})
        .off("keydown.fshLogin")
        .on("keydown.fshLogin", function (event) {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            this.click();
          }
        });
      this.$el.find("#btn-login").text("登录");
    }
  };
});
