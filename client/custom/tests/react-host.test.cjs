const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')

const source = fs.readFileSync(
  path.join(__dirname, '../src/views/fusanhe/react-host.js'),
  'utf8',
)

test('a require callback arriving after fallback timeout cannot remount React', async () => {
  let loadCallback
  let timerCallback
  let mounts = 0
  let View
  class EspoMain {
    remove() {}
  }
  vm.runInNewContext(source, {
    define(_name, _deps, factory) {
      View = factory(EspoMain, {})
    },
    require(_deps, success) {
      loadCallback = success
    },
    setTimeout(callback) {
      timerCallback = callback
      return 1
    },
    clearTimeout() {},
  })
  const view = new View()
  const element = { isConnected: true }
  view.$el = { find: () => ({ 0: element }) }
  view.getReactHost = () => ({})
  const mounting = view.mountScreen('service', {}, element)
  timerCallback()
  assert.equal(await mounting, false)
  loadCallback({
    mount() {
      mounts += 1
      return {}
    },
  })
  assert.equal(mounts, 0)
})
