define('custom:handlers/login/workspace', [], function () {
  return class {
    process() {
      const authorization = btoa('**workspace:public-workspace');
      return Promise.resolve({
        'Authorization': 'Basic ' + authorization,
        'Espo-Authorization': authorization,
      });
    }
  };
});
