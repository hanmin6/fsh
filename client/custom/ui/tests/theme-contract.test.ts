// @vitest-environment jsdom
import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import postcss from "postcss"
import { describe, expect, it } from "vitest"
import { buttonVariants } from "../src/components/ui/button"
import { hostUsesDarkTheme } from "../src/lib/theme"

const builtCss = readFileSync(
  resolve(process.cwd(), "../res/fusanhe/ui.css"),
  "utf8",
)
const css = postcss.parse(builtCss)

function tokens(selector: string) {
  const values = new Map<string, string>()
  css.walkRules((rule) => {
    if (rule.selector !== selector) return
    rule.walkDecls((declaration) => values.set(declaration.prop, declaration.value))
  })
  return values
}

function luminance(hex: string) {
  const channels = (hex.match(/[0-9a-f]{2}/gi) || []).map((part) => {
    const value = Number.parseInt(part, 16) / 255
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
  })
  return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722
}

function contrast(foreground: string, background: string) {
  const a = luminance(foreground)
  const b = luminance(background)
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
}

describe("Espo and shadcn cascade boundary", () => {
  it("follows the rendered Espo surface instead of macOS dark preference", () => {
    const root = document.createElement("div")
    const previous = document.body.style.backgroundColor
    try {
      document.body.style.backgroundColor = "rgb(247, 245, 239)"
      expect(hostUsesDarkTheme(root)).toBe(false)
      document.body.style.backgroundColor = "rgb(20, 24, 22)"
      expect(hostUsesDarkTheme(root)).toBe(true)
      root.dataset.theme = "light"
      expect(hostUsesDarkTheme(root)).toBe(false)
    } finally {
      document.body.style.backgroundColor = previous
    }
  })

  it("emits scoped, unlayered utilities so native anchor rules cannot override variants", () => {
    let utilityRules = 0
    css.walkRules((rule) => {
      if (!rule.selector?.includes("[data-fsh-ui-root]")) return
      if (!rule.selector.includes(".text-primary-foreground") &&
          !rule.selector.includes(".text-foreground") &&
          !rule.selector.includes(".bg-background")) return
      utilityRules += 1
      let parent = rule.parent
      while (parent && parent.type !== "root") {
        expect(parent.type === "atrule" && parent.name === "layer").toBe(false)
        parent = parent.parent
      }
    })
    expect(utilityRules).toBeGreaterThan(2)
    expect(buttonVariants({ variant: "outline" })).toContain("text-foreground")
    expect(buttonVariants({ variant: "outline" })).toContain("bg-background")
  })

  it("gives plain links at least 4.5:1 contrast in light and dark modes", () => {
    for (const selector of ["[data-fsh-ui-root]", "[data-fsh-ui-root].dark"]) {
      const values = tokens(selector)
      const background = values.get("--background")
      expect(background).toMatch(/^#[0-9a-f]{6}$/i)
      for (const key of ["--fsh-link", "--fsh-link-hover", "--foreground"]) {
        expect(contrast(values.get(key)!, background!)).toBeGreaterThanOrEqual(4.5)
      }
    }
    expect(builtCss).toContain("a:where(:not([data-slot])){color:var(--fsh-link)}")
  })
})
