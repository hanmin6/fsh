function backgroundLuminance(value: string): number | null {
  const match = value.match(/^rgba?\(([^)]+)\)$/i)
  if (!match) return null
  const components = match[1].match(/[\d.]+/g)?.map(Number)
  if (!components || components.length < 3) return null
  if (components.length > 3 && components[3] === 0) return null
  const channels = components.slice(0, 3).map((channel) => {
    const value = channel / 255
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
  })
  return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722
}

/**
 * Match Espo's actual rendered surface. The browser's OS color preference
 * alone is not authoritative: this Espo installation may intentionally use
 * its light theme while macOS is dark.
 */
export function hostUsesDarkTheme(target: HTMLElement): boolean {
  if (target.dataset.theme === "dark") return true
  if (target.dataset.theme === "light") return false

  const bodyLuminance = backgroundLuminance(getComputedStyle(document.body).backgroundColor)
  if (bodyLuminance !== null) return bodyLuminance < 0.25

  for (const element of [document.body, document.documentElement]) {
    const declared = element.getAttribute("data-theme")
    if (declared === "dark") return true
    if (declared === "light") return false
    if (element.classList.contains("dark") || element.classList.contains("theme-dark")) return true
  }
  const htmlLuminance = backgroundLuminance(
    getComputedStyle(document.documentElement).backgroundColor,
  )
  return htmlLuminance !== null && htmlLuminance < 0.25
}
