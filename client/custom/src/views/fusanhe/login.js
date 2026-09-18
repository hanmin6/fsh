define('custom:views/fusanhe/login', ['views/login'], function (Dep) {
    return class extends Dep {
        remove() { this.$el.removeClass('fsh-login'); return super.remove(); }
        afterRender() {
            super.afterRender();
            this.$el.addClass('fsh-login');
            const login=this.$el.find('#login');
            login.find('.logo').attr({src:'client/custom/res/fusanhe/logo-full.png',alt:'福三和 Fusanhe'});
            login.find('.panel-heading').append('<div class="fsh-login-heading"><h1>广州福三和食品有限公司</h1><p>Guangzhou Fusanhe Food Co., Ltd.</p><h2>外贸客户与询盘工作台</h2></div>');
            login.before('<div class="fsh-login-photo" role="img" aria-label="福三和广州工厂"></div>');
            this.$el.find('#btn-login').text('登录');
        }
    };
});
