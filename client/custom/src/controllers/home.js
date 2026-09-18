define('custom:controllers/home', ['controllers/home'], function (Dep) {
    return class extends Dep { actionIndex() { this.main('custom:views/fusanhe/home'); } };
});
