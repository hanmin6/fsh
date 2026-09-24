/**
 * EspoCRM owns authentication, permissions, navigation, and all writes.
 * React screens receive this narrow bridge; they never read cookies or
 * duplicate the server's authorization rules.
 */
export interface OutboundState {
  paused: boolean | null
  status: "paused" | "active" | "unknown"
}

export interface HostBridge {
  api: {
    get<T = unknown>(route: string, params?: Record<string, unknown>): Promise<T>
    post<T = unknown>(route: string, body?: unknown): Promise<T>
    patch<T = unknown>(route: string, body?: unknown): Promise<T>
  }
  can(scope: string, action?: string): boolean
  navigate(hash: string): void
  translate(label: string): string
  notify(message: string, type?: "success" | "error" | "info"): void
  currentUserId: string | null
  getOutboundState(): Promise<OutboundState>
}

export interface ScreenProps<T = unknown> {
  host: HostBridge
  data: T
  screen: string
}
