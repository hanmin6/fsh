const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')

const source = fs.readFileSync(path.join(__dirname, '../src/views/fusanhe/service-home.js'), 'utf8')

function serviceView(mountResult, canRead = true) {
  const events = []
  const nodes = new Map()
  const node = (selector) => {
    if (!nodes.has(selector)) {
      nodes.set(selector, {
        0: selector === '.fsh-ui-mount' ? { isConnected: true } : undefined,
        removeAttr(name) { events.push([selector, 'removeAttr', name]); return this },
        hide() { events.push([selector, 'hide']); return this },
        remove() { events.push([selector, 'remove']); return this },
        on(name) { events.push([selector, 'on', name]); return this },
      })
    }
    return nodes.get(selector)
  }
  let View
  class ReactHost {
    afterRender() {}
    mountScreen() { return mountResult }
    remove() { events.push(['view', 'remove']); return 'removed' }
  }
  vm.runInNewContext(source, {
    define(_name, _deps, factory) { View = factory(ReactHost, {}, {}) },
  })
  const view = new View()
  view.$el = { find: node }
  view.getAcl = () => ({ checkScope: () => canRead })
  view.load = () => { events.push(['view', 'legacyLoad']) }
  return { view, events }
}

test('service page mounts the new screen without running legacy data loads', async () => {
  const { view, events } = serviceView(Promise.resolve(true))
  await view.afterRender()
  assert.deepEqual(events, [['.fsh-ui-mount', 'removeAttr', 'aria-busy']])
})

test('service page retains the legacy view if the optional bundle fails', async () => {
  const { view, events } = serviceView(Promise.resolve(false), false)
  await view.afterRender()
  assert.ok(events.some(([selector, action]) => selector === '.fsh-legacy' && action === 'removeAttr'))
  assert.ok(events.some(([selector, action]) => selector === '.fsh-insights-entry' && action === 'remove'))
  assert.equal(events.filter(([selector, action]) => selector === 'view' && action === 'legacyLoad').length, 1)
})

test('late mount failure does not revive the service page after route removal', async () => {
  let resolveMount
  const pending = new Promise((resolve) => { resolveMount = resolve })
  const { view, events } = serviceView(pending)
  const rendering = view.afterRender()
  assert.equal(view.remove(), 'removed')
  resolveMount(false)
  await rendering
  assert.ok(!events.some(([selector, action]) => selector === 'view' && action === 'legacyLoad'))
})
