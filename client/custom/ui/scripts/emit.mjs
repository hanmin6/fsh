import { readFile, mkdir, writeFile } from "node:fs/promises"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import postcss from "postcss"
import prefixSelector from "postcss-prefix-selector"

const project = resolve(dirname(fileURLToPath(import.meta.url)), "..")
const prefix = "[data-fsh-ui-root]"
const checkOnly = process.argv.includes("--check")

const rawJs = await readFile(resolve(project, "dist/ui-runtime.js"), "utf8")
if (!/define\(\[(["'`])exports\1\],/.test(rawJs)) {
  throw new Error("Vite did not emit the expected AMD-compatible UMD wrapper")
}
const namedJs = rawJs.replace(
  /define\(\[(["'`])exports\1\],/,
  'define("custom:fusanhe/ui-runtime",["exports"],',
).replace(/^[ \t]+$/gm, "")
if (/\bprocess\.env\.NODE_ENV\b/.test(namedJs)) {
  throw new Error("Runtime bundle contains a Node-only process.env reference")
}
if (/https?:\/\//.test(rawJs)) {
  // React copyright URLs may appear in license banners. Detect load-bearing
  // network requests instead of rejecting inert comments or strings.
  if (/(?:import\s*\(|fetch\s*\(|src\s*=)\s*["'`]https?:\/\//.test(rawJs)) {
    throw new Error("Runtime bundle contains a remote asset request")
  }
}

const rawCss = await readFile(resolve(project, "dist/ui.css"), "utf8")
const result = await postcss([
  {
    postcssPlugin: "fsh-unlayer-utilities",
    Once(root) {
      // Espo's native styles are unlayered. Keeping Tailwind utilities inside
      // a layer lets even Espo's generic `a` rule win over Button text colors.
      // The emitted rules remain scoped and retain their normal specificity.
      root.walkAtRules("layer", (rule) => {
        if (rule.params.trim() === "utilities") {
          rule.replaceWith(...(rule.nodes || []))
        }
      })
    },
  },
  prefixSelector({
    prefix,
    transform(_prefix, selector, prefixedSelector) {
      if (selector === ":root" || selector === ":host") return prefix
      if (selector.startsWith(prefix)) return selector
      return prefixedSelector
    },
  }),
]).process(rawCss, { from: "dist/ui.css" })
const scopedCss = result.css
if (/(?:@import|url\(\s*["']?https?:)/i.test(scopedCss)) {
  throw new Error("Built CSS contains a remote import")
}
if (/(^|[},])\s*(?:body|html|:root)\s*\{/m.test(scopedCss)) {
  throw new Error("Built CSS contains an unscoped document selector")
}
const parsedCss = postcss.parse(scopedCss)
parsedCss.walkAtRules("layer", (rule) => {
  if (rule.params.trim() === "utilities") {
    throw new Error("Built utilities must not remain cascade-layered under Espo")
  }
})
parsedCss.walkRules((rule) => {
  if (rule.parent?.name?.includes("keyframes")) return
  for (const selector of rule.selectors || []) {
    if (!selector.includes(prefix)) {
      throw new Error(`Built CSS has an unscoped selector: ${selector}`)
    }
  }
})

const outputs = [
  [resolve(project, "../src/fusanhe/ui-runtime.js"), namedJs],
  [resolve(project, "../res/fusanhe/ui.css"), scopedCss],
]
for (const [file, content] of outputs) {
  if (checkOnly) {
    const current = await readFile(file, "utf8").catch(() => "")
    if (current !== content) throw new Error(`Generated asset is stale: ${file}`)
  } else {
    await mkdir(dirname(file), { recursive: true })
    await writeFile(file, content)
  }
}
