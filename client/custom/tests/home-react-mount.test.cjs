const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')

function load(name, mountResult) {
  const source = fs.readFileSync(path.join(__dirname, `../src/views/fusanhe/${name}.js`), 'utf8')
  const events = []
  const nodes = new Map()
  const node = selector => {
    if (!nodes.has(selector)) nodes.set(selector, {
      0: selector === '.fsh-ui-mount' ? { isConnected: true } : undefined,
      removeAttr(value) { events.push([selector, 'removeAttr', value]); return this },
      hide() { events.push([selector, 'hide']); return this },
      html(value) { events.push([selector, 'html', value]); return this },
      on(value) { events.push([selector, 'on', value]); return this },
      remove() { events.push([selector, 'remove']); return this },
    })
    return nodes.get(selector)
  }
  let View
  class ReactHost {
    afterRender() {}
    mountScreen(screen) { events.push(['view', 'mount', screen]); return mountResult }
    remove() { events.push(['view', 'remove']); return 'removed' }
  }
  vm.runInNewContext(source, { define(_name, _deps, factory) { View = factory(ReactHost, {}, {}) } })
  const view = new View()
  view.$el = { find: node }
  view.getAcl = () => ({ checkScope: () => true })
  view.render = () => { events.push(['view', 'legacyLoad']) }
  view.load = () => { events.push(['view', 'legacyLoad']) }
  view.loadInsights = () => { events.push(['view', 'legacyLoad']) }
  view.requestVersion = 0
  view.detailVersion = 0
  return { view, events }
}

for (const [name, screen] of [['home', 'home'], ['crm-home', 'crm'], ['insights', 'insights']]) {
  test(`${name} mounts ${screen} without legacy requests`, async () => {
    const { view, events } = load(name, Promise.resolve(true))
    await view.afterRender()
    assert.ok(events.some(([scope, action, value]) => scope === 'view' && action === 'mount' && value === screen))
    assert.equal(events.filter(([scope, action]) => scope === 'view' && action === 'legacyLoad').length, 0)
  })

  test(`${name} retains legacy page when bundle is unavailable`, async () => {
    const { view, events } = load(name, Promise.resolve(false))
    await view.afterRender()
    assert.ok(events.some(([scope, action]) => scope === '.fsh-legacy' && action === 'removeAttr'))
    assert.equal(events.filter(([scope, action]) => scope === 'view' && action === 'legacyLoad').length, 1)
  })

  test(`${name} ignores a late mount failure after route removal`, async () => {
    let settle
    const { view, events } = load(name, new Promise(resolve => { settle = resolve }))
    const pending = view.afterRender()
    assert.equal(view.remove(), 'removed')
    settle(false)
    await pending
    assert.equal(events.filter(([scope, action]) => scope === 'view' && action === 'legacyLoad').length, 0)
  })
}
