// @vitest-environment jsdom
import * as React from "react"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { Button } from "../src/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "../src/components/ui/dialog"
import { PortalContainerProvider } from "../src/lib/portal"

describe("scoped Radix dialog", () => {
  it("keeps its portal, title, focus and close flow inside the mounted workbench", async () => {
    const root = document.createElement("div")
    root.setAttribute("data-fsh-ui-root", "")
    document.body.append(root)
    try {
      render(
        <PortalContainerProvider container={root}>
          <Dialog>
            <DialogTrigger asChild>
              <Button type="button">打开审核说明</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogTitle>审核说明</DialogTitle>
              <DialogDescription>请先核对客户身份。</DialogDescription>
              <Button type="button">核对身份</Button>
            </DialogContent>
          </Dialog>
        </PortalContainerProvider>,
        { container: root },
      )

      const trigger = screen.getByRole("button", { name: "打开审核说明" })
      trigger.focus()
      fireEvent.click(trigger)

      const dialog = await screen.findByRole("dialog", { name: "审核说明" })
      expect(root.contains(dialog)).toBe(true)
      expect(root.querySelector('[data-slot="dialog-overlay"]')).not.toBeNull()
      expect(document.body.querySelector("body > [data-slot=dialog-content]")).toBeNull()
      expect(dialog.getAttribute("aria-labelledby")).toBeTruthy()
      await waitFor(() => expect(dialog.contains(document.activeElement)).toBe(true))

      fireEvent.keyDown(dialog, { key: "Escape" })
      await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())
      await waitFor(() => expect(document.activeElement).toBe(trigger))
    } finally {
      root.remove()
    }
  })
})
