define("custom:views/fusanhe/login", ["views/login"], function (Dep) {
  return class extends Dep {
    setup() {
      super.setup();
      if (this.workspaceEnabled()) {
        this.templateContent = '<div class="fsh-shell"><p class="fsh-empty" role="status">正在进入福三和工作台…</p></div>';
      }
    }
    workspaceEnabled() {
      return this.getConfig().get("loginData")?.method === "FusanheWorkspace" ||
        this.getConfig().get("authenticationMethod") === "FusanheWorkspace";
    }
    remove() {
      this.$el.removeClass("fsh-login");
      return super.remove();
    }
    afterRender() {
      if (this.workspaceEnabled()) {
        this.$el.html('<div class="fsh-shell"><p class="fsh-empty" role="status">正在进入福三和工作台…</p></div>');
        this.enterWorkspace();
        return;
      }
      super.afterRender();
      this.$el.addClass("fsh-login");
      const login = this.$el.find("#login");
      login.find(".logo").attr({
        src: "client/custom/res/fusanhe/logo-full.png",
        alt: "福三和 Fusanhe",
      });
      login
        .find(".panel-heading")
        .append(
          '<div class="fsh-login-heading"><h1>广州福三和食品有限公司</h1><p>Guangzhou Fusanhe Food Co., Ltd.</p><h2>外贸客户与询盘工作台</h2></div>',
        );
      login.before(
        '<div class="fsh-login-photo" role="img" aria-label="福三和广州工厂"></div>',
      );
      this.$el.find("#btn-login").text("登录");
    }
    async enterWorkspace() {
      // A public mode marker, never a stored account password or privileged token.
      const authorization = btoa("**workspace:public-workspace");
      try {
        const data = await Espo.Ajax.getRequest("App/user", null, {
          login: true,
          headers: {
            "Authorization": "Basic " + authorization,
            "Espo-Authorization": authorization,
            "Espo-Authorization-By-Token": "false",
            "Espo-Authorization-Create-Token-Secret": "true",
          },
        });
        this.trigger("login", data.user.userName, data);
      } catch (error) {
        error.errorIsHandled = true;
        this.$el.html('<div class="fsh-shell"><p role="alert">工作台暂时无法进入，请检查服务或联系维护人员。</p><button class="btn btn-default fsh-enter-retry" type="button">重新进入</button></div>');
        this.$el.find(".fsh-enter-retry").on("click", () => {
          this.$el.find(".fsh-enter-retry").prop("disabled", true);
          this.enterWorkspace();
        });
      }
    }
  };
});
