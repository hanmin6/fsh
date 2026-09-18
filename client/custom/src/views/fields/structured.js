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
      data.displayValue =
        items
          .map((x) =>
            this.name === "citedKnowledge"
              ? U.link(
                  "KnowledgeDocument",
                  typeof x === "string" ? x : x.id || x.documentId,
                  typeof x === "string"
                    ? "查看引用资料"
                    : x.name || x.title || "查看引用资料",
                )
              : U.escape(
                  typeof x === "string"
                    ? U.status(x)
                    : x.name || x.label || "资料",
                ),
          )
          .join("<br>") || "—";
      return data;
    }
  };
});
