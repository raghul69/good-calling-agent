import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

vi.mock("./auth", () => ({
  clearAccessToken: vi.fn(),
  getAccessToken: vi.fn().mockResolvedValue("test-token"),
}));

vi.mock("./lib/supabase", () => ({
  getAuthRedirectUrl: (path = "/agents") => `http://localhost${path}`,
  isSupabaseConfigured: true,
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: { access_token: "test-token" } } }),
      onAuthStateChange: vi.fn(() => ({ data: { subscription: { unsubscribe: vi.fn() } } })),
      signOut: vi.fn(),
    },
  },
}));

vi.mock("./lib/api", () => ({
  apiConnectionMessage: "Backend not connected. Add NEXT_PUBLIC_API_URL in Vercel production env.",
  isApiConfigured: true,
  api: {
    agents: vi.fn().mockResolvedValue([]),
    analytics: vi.fn().mockResolvedValue({
      total_calls: 0,
      answered_calls: 0,
      failed_calls: 0,
      total_bookings: 0,
      avg_duration: 0,
      average_duration: 0,
      total_minutes: 0,
      estimated_ai_cost: 0,
      booking_rate: 0,
    }),
    billing: vi.fn().mockResolvedValue({
      plan: "Launch",
      status: "trial",
      included_minutes: 250,
      used_minutes: 0,
      overage_minutes: 0,
      estimated_ai_cost: 0,
      next_invoice_estimate: 49,
    }),
    browserTest: vi.fn().mockResolvedValue({
      call_id: "call-1",
      dispatch_id: "dispatch-1",
      roomName: "browser-test",
      room: "browser-test",
      token: "token",
      url: "wss://example.livekit.cloud",
      status: "dispatched",
      started_at: "2026-04-29T00:00:00Z",
    }),
    calls: vi.fn().mockResolvedValue([]),
    callNow: vi.fn(),
    campaigns: vi.fn().mockResolvedValue([]),
    config: vi.fn().mockResolvedValue({}),
    contacts: vi.fn().mockResolvedValue([]),
    health: vi.fn().mockResolvedValue({}),
    sipHealth: vi.fn().mockResolvedValue({
      ok: false,
      trunk_configured: false,
      livekit_configured: false,
      sip_trunk_id: null,
      livekit: {},
    }),
    livekitHealth: vi.fn().mockResolvedValue({
      ok: false,
      livekit: {},
      room_count: null,
      api_reachable: false,
    }),
    sipTestCall: vi.fn(),
    outboundCall: vi.fn().mockResolvedValue({
      call_id: "call-2",
      room_name: "call-test",
      status: "dispatched",
      phone_number: "+918065480786",
    }),
    me: vi.fn().mockResolvedValue({ success: true, email: "test@example.com", role: "owner" }),
    saveConfig: vi.fn(),
    workspace: vi.fn().mockResolvedValue({ id: "workspace-1", name: "Personal", role: "owner", member_count: 1, settings: {} }),
  },
}));

/** Import + mount graph (jsdom). Failures here mirror blank-page import/render crashes. */
describe("App smoke", () => {
  beforeEach(() => {
    window.history.pushState({}, "", "/");
  });

  it("imports and renders landing without throwing", async () => {
    render(<App />);
    expect(await screen.findByRole("navigation")).toBeInTheDocument();
  });

  it("renders the authenticated agent setup shell", async () => {
    window.history.pushState({}, "", "/agents");
    render(<App />);

    expect(await screen.findByText("Your Agents")).toBeInTheDocument();
    expect(screen.getByText("Agent Welcome Message")).toBeInTheDocument();
    expect(screen.getByText("Agent Prompt")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /save agent/i })).toBeInTheDocument();
  });
});
