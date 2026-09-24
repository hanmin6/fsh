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
        length: 1,
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
async function renderTimeline(messages) {
  const html = {};
  const fields = {};
  const element = {
    prepend() { return this; },
    find(selector) {
      return (fields[selector] ||= {
        remove() { return this; },
        prepend() { return this; },
        html(value) { html[selector] = value; return this; },
        on() { return this; },
        attr() { return this; },
      });
    },
  };
  const responses = {
    ExternalMessage: { total: messages.length, list: messages },
    AIReplyDraft: { list: [] },
    ExternalConversation: { list: [{ id: "conversation-test" }] },
    OutboundTask: { list: [] },
  };
  const Class = load(
    "views/external-conversation/record/detail.js",
    {
      "views/record/detail": class {},
      ajax: { getRequest: async (entity) => responses[entity] },
      "custom:views/fusanhe/common": U,
    },
    { Espo: { Ui: { notify() {}, success() {}, error() {} } } },
  );
  const view = new Class();
  Object.assign(view, {
    $el: element,
    requestNumber: 0,
    getAcl: () => ({ checkScope: () => true }),
    model: {
      id: "conversation-test",
      attributes: { id: "conversation-test" },
      get: () => null,
    },
    renderIdentityCard: () => "",
    bindIdentityCard() {},
    renderHandoff() {},
    renderDraft() {},
  });
  await view.renderWorkbench();
  return html[".fsh-workspace-container"];
}
test("Escapes HTML content and URL identifiers", () => {
  assert.equal(
    U.escape('<img onerror="alert(1)">'),
    "&lt;img onerror=&quot;alert(1)&quot;&gt;",
  );
  assert.match(U.link("Lead", 'x"/#', "<b>"), /x%22%2F%23/);
  assert.equal(U.escape(0), "0");
});
test("Timeline renders safe attachment labels from MIC items and legacy formats", async () => {
  const html = await renderTimeline([
    {
      senderName: "Buyer",
      sentAt: "2026-09-23 10:00:00",
      body: "MIC inquiry",
      direction: "inbound",
      attachmentMetadata: {
        items: [
          {
            name: '<img src=x onerror="alert(1)">',
            mediaType: 'application/<script>alert("x")</script>',
            size: 1536,
            url: "https://private.example/token-secret",
          },
        ],
      },
    },
    {
      senderName: "Legacy array",
      sentAt: "2026-09-23 10:01:00",
      body: "Array format",
      direction: "inbound",
      attachmentMetadata: [{ name: "array.pdf" }],
    },
    {
      senderName: "Legacy files",
      sentAt: "2026-09-23 10:02:00",
      body: "Files format",
      direction: "inbound",
      attachmentMetadata: { files: [{ fileName: "legacy.xlsx" }] },
    },
  ]);
  assert.match(html, /&lt;img src=x onerror=&quot;alert\(1\)&quot;&gt;/);
  assert.match(html, /application\/&lt;script&gt;alert\(&quot;x&quot;\)&lt;\/script&gt;/);
  assert.match(html, /1\.5 KB/);
  assert.match(html, /array\.pdf/);
  assert.match(html, /legacy\.xlsx/);
  assert.doesNotMatch(html, /<img|<script|private\.example|token-secret/);
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
test("Entry page metrics are read-only totals, ACL-gated, no full scans", async () => {
  let requests = [];
  const Class = load("views/fusanhe/home.js", {
    "views/main": class {},
    ajax: {
      getRequest: async (entity, params) => {
        requests.push([entity, params]);
        return { total: 201, list: [{ id: "1" }] };
      },
    },
    "custom:views/fusanhe/common": U,
  });
  const view = new Class();
  view.getAcl = () => ({ checkScope: () => true });
  view.getUser = () => ({ id: "u1" });
  const rows = await view.counts([["Task", { type: "equals", attribute: "assignedUserId", value: "u1" }]]);
  assert.equal(rows[0], 201);
  assert.equal(requests.length, 1);
  assert.equal(requests[0][0], "Task");
  assert.equal(requests[0][1].maxSize, 1, "counts use total of a 1-row query instead of scanning all rows");
  requests = [];
  view.getAcl = () => ({ checkScope: () => false });
  const denied = await view.counts([["AIReplyDraft", null]]);
  assert.equal(denied[0], "无权限");
  assert.equal(requests.length, 0, "no request is issued without read permission");
});
test("Entry page renders both module links only when the scope is readable", async () => {
  const Class = load("views/fusanhe/home.js", {
    "views/main": class {},
    ajax: { getRequest: async () => ({ total: 3, list: [] }) },
    "custom:views/fusanhe/common": U,
  });
  const view = new Class();
  view.getAcl = () => ({ checkScope: (scope) => scope !== "ExternalConversation" });
  view.getUser = () => ({ id: "u1" });
  const html = {};
  view.$el = {
    find: (selector) => (html[selector] ||= {
      html(v) { html[selector] = v; return this; },
    }),
  };
  await view.render();
  assert.match(html[".fsh-entry-body"], /#Home\/crm/);
  assert.doesNotMatch(html[".fsh-entry-body"], /#Home\/service/);
});

test("Phase 1 statuses translate: replied, control modes and mock receipts", () => {
  assert.equal(U.status("replied"), "已回复");
  assert.equal(U.status("aiAssist"), "AI 辅助");
  assert.equal(U.status("human"), "人工接管");
  assert.equal(U.status("mockSent"), "模拟已发送");
  assert.match(U.badge("mockSent"), /模拟已发送/);
  assert.match(U.badge("human"), /fsh-warning/);
});
test("Unlinked identity card never links silently and offers explicit actions", () => {
  const { view, html } = createDetail({ id: "d", status: "generated", draftText: "x" });
  view.model.attributes = { identityId: "i1" };
  view.identity = { linkStatus: "unlinked", channelType: "Alibaba", externalUserId: "buyer-1" };
  const card = view.renderIdentityCard();
  html[".identity-card"] = card;
  assert.match(card, /待确认/);
  assert.match(card, /建立线索建档/);
  assert.match(card, /查找匹配客户/);
  assert.match(card, /人工确认/, "weak evidence must not auto-link");
  view.identity = { linkStatus: "confirmed", channelType: "Alibaba", leadId: "l1", leadName: "Acme" };
  const confirmed = view.renderIdentityCard();
  assert.match(confirmed, /已确认/);
  assert.match(confirmed, /#Lead\/view\/l1/);
  assert.doesNotMatch(confirmed, /建立线索建档/, "confirmed identities offer no relink actions");
});
test("Handoff section is hidden without Task create permission", () => {
  const noTask = createDetail({ id: "d", status: "generated", draftText: "x" }, false);
  noTask.view.renderHandoff();
  assert.match(noTask.html[".fsh-handoff-area"], /没有创建跟进任务的权限/);
});
