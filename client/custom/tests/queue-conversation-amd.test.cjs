const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const root = path.resolve(__dirname, '..', 'src')
function load(relative, deps) {
  let Klass
  vm.runInNewContext(fs.readFileSync(path.join(root, relative), 'utf8'), {
    define: (_name, names, factory) => { Klass = factory(...names.map(name => deps[name])) },
    Date, console,
  })
  return Klass
}
class Host {
  setup() {}
  afterRender() {}
  mountScreen(screen, data) { this.mounted = [screen, data]; return Promise.resolve(true) }
  unmountScreen() { this.unmounted = (this.unmounted || 0) + 1 }
  getReactHost() { return { api: {} } }
  remove() { this.removed = true }
}
function jqueryElement() {
  const mount = { isConnected: true }
  return {
    find(selector) {
      if (selector === '.fsh-ui-mount') return { 0: mount }
      if (selector === '.fsh-workspace-container') return { length: 1, remove() {} }
      return { length: 0 }
    },
    prepend() {},
  }
}
test('five queue types mount their React screen with metadata status options', async () => {
  const List = load('views/fusanhe/list.js', {
    'custom:views/fusanhe/react-host': Host,
    ajax: {},
    'custom:views/fusanhe/common': {},
  })
  for (const entity of ['ExternalConversation','AIReplyDraft','KnowledgeDocument','OutboundTask','AutomationAgent']) {
    const view = new List()
    view.options = { scope: entity }
    view.$el = jqueryElement()
    view.getMetadata = () => ({ get: () => ['pending'] })
    view.setup()
    view.afterRender()
    await Promise.resolve()
    assert.equal(view.mounted[0], 'queue')
    assert.equal(view.mounted[1].entity, entity)
    assert.equal(view.mounted[1].statusOptions[0], 'pending')
  }
})
test('detail mounts through borrowed host bridge, then unmounts before native removal', async () => {
  const Detail = load('views/external-conversation/record/detail.js', {
    'views/record/detail': class { setup() {} afterRender() {} remove() { this.removed = true } },
    ajax: {},
    'custom:views/fusanhe/common': {},
    'custom:views/fusanhe/react-host': Host,
  })
  const view = new Detail()
  view.$el = jqueryElement()
  view.model = { id: 'conv-1', attributes: { name: 'Example' } }
  view.setup()
  await view.renderWorkbench()
  assert.equal(view.mounted[0], 'conversation')
  assert.equal(view.mounted[1].conversationId, 'conv-1')
  assert.ok(view.getReactHost().api)
  view.remove()
  assert.equal(view.unmounted, 1)
  assert.equal(view.removed, true)
})
