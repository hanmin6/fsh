define("custom:views/fields/structured", [
  "views/fields/base",
  "custom:views/fusanhe/common",
], function (Dep, U) {
  return class extends Dep {
    editTemplateContent = "{{{displayValue}}}";
    fetch() {
      return {};
    }
    detailTemplateContent = "{{{displayValue}}}";
    listTemplateContent = "{{{displayValue}}}";
    data() {
      const data = super.data();
      const value = this.model.get(this.name);
      const items = Array.isArray(value) ? value : [];
      const t = (label) => this.translate(label, "labels", "Fusanhe");
      const canReadKnowledge = this.getAcl()?.checkScope?.("KnowledgeDocument", "read") ?? false;
      data.displayValue =
        items
          .map((x) => {
            if (this.name === "citedKnowledge") {
              const id = typeof x === "string" ? x : x?.id || x?.documentId;
              const label = typeof x === "string" ? t("查看引用资料") : x?.name || x?.title || t("查看引用资料");
              return canReadKnowledge && id
                ? U.link("KnowledgeDocument", id, label)
                : U.escape(label);
            }
            const label = typeof x === "string" ? U.status(x) : x?.name || x?.label || t("资料");
            return U.escape(typeof x === "string" ? t(label) : label);
          })
          .join("<br>") || "—";
      return data;
    }
  };
});
