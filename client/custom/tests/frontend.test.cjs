const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const root = path.resolve(__dirname, "..");
function load(name, dependencies, extra = {}) {
  let result;
  vm.runInNewContext(fs.readFileSync(path.join(root, "src", name), "utf8"), {
    define: (id, names, factory) => {
      result = factory(...names.map((n) => dependencies[n]));
    },
    $: () => {
      let value;
      return {
        text(v) {
          value = String(v);
          return this;
        },
        html() {
          return value
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
        },
      };
    },
    Date,
    console,
    ...extra,
  });
  return result;
}
const U = load("views/fusanhe/common.js", {});
function createDetail(draft, can = true) {
  const html = {},
    handlers = {},
    calls = [];
  const fields = {};
  const element = {
    find(selector) {
      return (fields[selector] ||= {
        html(value) {
          html[selector] = value;
          return this;
        },
        on(event, fn) {
          handlers[selector + ":" + event] = fn;
          return this;
        },
        prop() {
          return this;
        },
        empty() {
          html[selector] = "";
        },
        val() {
          return draft.draftText;
        },
      });
    },
  };
  const Ajax = {
    postRequest: async (...args) => calls.push(["post", ...args]),
    patchRequest: async (...args) => calls.push(["patch", ...args]),
  };
  const Class = load(
    "views/external-conversation/record/detail.js",
    {
      "views/record/detail": class {},
      ajax: Ajax,
      "custom:views/fusanhe/common": U,
    },
    { Espo: { Ui: { notify() {}, success() {}, error() {} } } },
  );
  const view = new Class();
  Object.assign(view, {
    $el: element,
    currentDraft: draft,
    getAcl: () => ({ checkScope: () => can }),
    renderWorkbench: async () => {},
    model: { id: "conversation-test", fetch: async () => {} },
  });
  view.renderDraft();
  return { view, html, handlers, calls };
}
test("Escapes HTML content and URL identifiers", () => {
  assert.equal(
    U.escape('<img onerror="alert(1)">'),
    "&lt;img onerror=&quot;alert(1)&quot;&gt;",
  );
  assert.match(U.link("Lead", 'x"/#', "<b>"), /x%22%2F%23/);
  assert.equal(U.escape(0), "0");
});
test("Waiting minutes handles missing and future timestamps", () => {
  assert.equal(U.wait(null), null);
  assert.equal(U.wait("2099-01-01 00:00:00"), 0);
});
test("Sent drafts cannot be edited, rejected, or approved in review UI", () => {
  const { html, calls } = createDetail({
    id: "d",
    status: "sent",
    riskLevel: "low",
    draftText: "Sent",
  });
  assert.match(html[".fsh-draft-area"], /textarea[^>]+readonly/);
  for (const cls of ["fsh-save", "fsh-reject", "fsh-approve"])
    assert.match(html[".fsh-draft-area"], new RegExp(cls + '" disabled'));
  assert.equal(calls.length, 0);
});
test("High-risk generated draft requires explicit second confirmation", () => {
  const { html, handlers, calls } = createDetail({
    id: "d",
    status: "generated",
    riskLevel: "high",
    draftText: "Draft",
  });
  assert.match(html[".fsh-draft-area"], /MOQ/);
  handlers[".fsh-approve:click"]();
  assert.match(html[".fsh-confirm-area"], /fsh-confirm-submit" disabled/);
  assert.match(html[".fsh-confirm-area"], /我已完成人工审核/);
  assert.equal(calls.length, 0);
});
test("Saving only patches draft; it never creates an outbound task", async () => {
  const { view, calls } = createDetail({
    id: "draft-test",
    status: "generated",
    draftText: "Revised",
  });
  await view.saveDraft(false);
  assert.equal(calls.length, 1);
  assert.equal(calls[0][0], "patch");
  assert.equal(calls[0][1], "AIReplyDraft/draft-test");
  assert.equal(calls[0][2].status, "edited");
});
test("Rejection only patches rejection status", async () => {
  const { view, calls } = createDetail({
    id: "draft-test",
    status: "generated",
    draftText: "Draft",
  });
  await view.saveDraft(true);
  assert.equal(calls[0][0], "patch");
  assert.equal(calls[0][2].status, "rejected");
});
test("Empty reply cannot be approved", async () => {
  const { view, calls } = createDetail({
    id: "draft-test",
    status: "generated",
    draftText: "  ",
  });
  await view.approveDraft("draft-test");
  assert.equal(calls.length, 0);
});
test("Dashboard fetch is read only and paginates all accessible rows", async () => {
  let requests = [];
  const Class = load("views/fusanhe/home.js", {
    "views/main": class {},
    ajax: {
      getRequest: async (entity, params) => {
        requests.push(params);
        return {
          total: 201,
          list: Array.from(
            { length: params.offset === 0 ? 200 : 1 },
            (_, i) => ({ id: String(params.offset + i) }),
          ),
        };
      },
    },
    "custom:views/fusanhe/common": U,
  });
  const view = new Class();
  view.getAcl = () => ({ checkScope: () => true });
  const rows = await view.fetchAll("ExternalConversation", ["id"]);
  assert.equal(rows.length, 201);
  assert.equal(requests[1].offset, 200);
  view.getAcl = () => ({ checkScope: () => false });
  assert.equal(await view.fetchAll("AIReplyDraft", ["id"]), null);
  assert.equal(requests.length, 2);
});
