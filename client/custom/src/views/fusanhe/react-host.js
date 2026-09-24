define("custom:views/fusanhe/react-host", ["views/main", "ajax"], function (Dep, Ajax) {
  return class extends Dep {
    /**
     * Mount a React screen in an existing content element. This promise
     * resolves false if the optional bundle is unavailable, so a legacy AMD
     * view can render its previous markup as a visible fallback.
     */
    mountScreen(screen, data, target) {
      this.unmountScreen();
      const generation = this._fshGeneration;
      const element =
        typeof target === "string"
          ? this.$el.find(target)[0]
          : target || this.$el.find(".fsh-ui-mount")[0];
      if (!element) return Promise.resolve(false);

      return new Promise((resolve) => {
        let settled = false;
        const finish = (ok) => {
          if (settled) return;
          settled = true;
          clearTimeout(timeout);
          resolve(ok);
        };
        const timeout = setTimeout(() => finish(false), 10000);
        try {
          require(
            ["custom:fusanhe/ui-runtime"],
            (runtime) => {
              if (generation !== this._fshGeneration || !element.isConnected) {
                finish(false);
                return;
              }
              try {
                this._fshHandle = runtime.mount(
                  element,
                  screen,
                  this.getReactHost(),
                  data,
                );
                this._fshRuntime = runtime;
                finish(true);
              } catch (error) {
                this._fshHandle = null;
                finish(false);
              }
            },
            () => finish(false),
          );
        } catch (error) {
          finish(false);
        }
      });
    }

    updateScreen(data) {
      if (!this._fshHandle || !this._fshRuntime) return false;
      this._fshRuntime.update(this._fshHandle, data);
      return true;
    }

    unmountScreen() {
      this._fshGeneration = (this._fshGeneration || 0) + 1;
      if (this._fshHandle && this._fshRuntime) {
        this._fshRuntime.unmount(this._fshHandle);
      }
      this._fshHandle = null;
      this._fshRuntime = null;
    }

    getReactHost() {
      return {
        api: {
          get: (route, params) => Ajax.getRequest(route, params),
          post: (route, body) => Ajax.postRequest(route, body),
          patch: (route, body) => Ajax.patchRequest(route, body),
        },
        can: (scope, action = "read") => {
          try {
            return !!this.getAcl().checkScope(scope, action);
          } catch (error) {
            return false;
          }
        },
        navigate: (hash) => {
          if (typeof hash !== "string" || !hash.startsWith("#")) return;
          this.getRouter().navigate(hash, { trigger: true });
        },
        translate: (label) => {
          const language = this.getLanguage();
          return language?.has(label, "labels", "Fusanhe")
            ? language.translate(label, "labels", "Fusanhe")
            : label;
        },
        notify: (message, type = "info") => {
          if (type === "success") Espo.Ui.success(message);
          else if (type === "error") Espo.Ui.error(message);
          else Espo.Ui.notify(message);
        },
        currentUserId: this.getUser()?.id || null,
        getOutboundState: async () => {
          if (!this.getAcl()?.checkScope("ExternalConversation", "read")) {
            return { paused: null, status: "unknown" };
          }
          try {
            const response = await Ajax.getRequest("Fusanhe/status");
            const paused =
              typeof response?.outboundPaused === "boolean"
                ? response.outboundPaused
                : null;
            return {
              paused,
              status:
                paused === null ? "unknown" : paused ? "paused" : "active",
            };
          } catch (error) {
            return { paused: null, status: "unknown" };
          }
        },
      };
    }

    remove() {
      this.unmountScreen();
      return super.remove();
    }
  };
});
