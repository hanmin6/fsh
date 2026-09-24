import * as React from "react"
import { createRoot, type Root } from "react-dom/client"
import { TooltipProvider } from "@/components/ui/tooltip"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { PortalContainerProvider } from "@/lib/portal"
import type { HostBridge, ScreenProps } from "@/lib/host"
import "./styles.css"

type ScreenModule = { default: React.ComponentType<ScreenProps<any>>; screenId?: string }

// Screen ownership belongs to feature agents. New screens are discovered at
// build time, so the shared entry and lockfile do not need concurrent edits.
const modules = import.meta.glob<ScreenModule>("./screens/**/*.tsx", { eager: true })
const screens = new Map<string, React.ComponentType<ScreenProps<any>>>()
for (const [path, module] of Object.entries(modules)) {
  const fallbackId = path.split("/").pop()?.replace(/\.tsx$/, "")
  const id = module.screenId || fallbackId
  if (id && module.default) screens.set(id, module.default)
}

export interface MountHandle {
  target: HTMLElement
  root: Root
  screen: string
  host: HostBridge
  disposed: boolean
  cleanupTheme: () => void
}

class ScreenErrorBoundary extends React.Component<
  { host: HostBridge; children: React.ReactNode },
  { failed: boolean }
> {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  render() {
    if (this.state.failed) {
      return (
        <Alert variant="destructive">
          <AlertTitle>{this.props.host.translate("页面暂时无法显示")}</AlertTitle>
          <AlertDescription>
            {this.props.host.translate("请刷新页面重试。")}
            <Button variant="outline" type="button" onClick={() => window.location.reload()}>
              {this.props.host.translate("刷新页面")}
            </Button>
          </AlertDescription>
        </Alert>
      )
    }
    return this.props.children
  }
}

function watchTheme(target: HTMLElement) {
  const media = window.matchMedia("(prefers-color-scheme: dark)")
  const sync = () => {
    target.classList.toggle(
      "dark",
      target.dataset.theme === "dark" ||
        (target.dataset.theme !== "light" &&
          (document.documentElement.classList.contains("dark") || media.matches)),
    )
  }
  const observer = new MutationObserver(sync)
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] })
  media.addEventListener("change", sync)
  sync()
  return () => {
    observer.disconnect()
    media.removeEventListener("change", sync)
    target.classList.remove("dark")
  }
}

function render(handle: MountHandle, data: unknown) {
  const Screen = screens.get(handle.screen)
  if (!Screen) throw new Error(`Unknown Fusanhe screen: ${handle.screen}`)
  handle.root.render(
    <PortalContainerProvider container={handle.target}>
      <TooltipProvider delayDuration={250}>
        <ScreenErrorBoundary host={handle.host}>
          <Screen host={handle.host} data={data} screen={handle.screen} />
        </ScreenErrorBoundary>
      </TooltipProvider>
    </PortalContainerProvider>,
  )
}

export function mount(
  target: HTMLElement,
  screen: string,
  host: HostBridge,
  data: unknown = null,
): MountHandle {
  if (!target || !target.isConnected) throw new Error("Fusanhe mount target is detached")
  if (!screens.has(screen)) throw new Error(`Unknown Fusanhe screen: ${screen}`)
  target.setAttribute("data-fsh-ui-root", "")
  const cleanupTheme = watchTheme(target)
  const root = createRoot(target)
  const handle: MountHandle = { target, root, screen, host, disposed: false, cleanupTheme }
  render(handle, data)
  return handle
}

export function update(handle: MountHandle, data: unknown) {
  if (handle.disposed || !handle.target.isConnected) return
  render(handle, data)
}

export function unmount(handle: MountHandle) {
  if (handle.disposed) return
  handle.disposed = true
  handle.root.unmount()
  handle.cleanupTheme()
  handle.target.removeAttribute("data-fsh-ui-root")
}

export function availableScreens() {
  return [...screens.keys()]
}
