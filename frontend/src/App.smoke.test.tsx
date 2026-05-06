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

vi.mock("./lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./lib/api")>();
  return {
    ...actual,
    apiConnectionMessage: "Backend not connected. Add NEXT_PUBLIC_API_URL in Vercel production env.",
    isApiConfigured: true,
    api: {
      agents: vi.fn().mockResolvedValue([
        {
          id: "a0123456789abcdef0123456789abcd32",
          name: "Smoke Agent",
          active_version_id: "b0123456789abcdef0123456789abcd32",
          active_version: {
            id: "b0123456789abcdef0123456789abcd32",
            version: 1,
            status: "draft",
            welcome_message: "Welcome smoke",
            system_prompt: "Smoke prompt",
          },
        },
      ]),
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
      stripe_configured: true,
    }),
    createCheckout: vi.fn().mockResolvedValue({ url: "https://checkout.stripe.test/session", id: "cs_test_1" }),
    billingPortal: vi.fn().mockResolvedValue({ url: "https://billing.stripe.test/session" }),
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
    callsList: vi.fn().mockResolvedValue({
      items: [],
      limit: 25,
      offset: 0,
      has_more: false,
    }),
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
    providerOptions: vi.fn().mockResolvedValue({
      llm_providers: [{ id: "groq", label: "Groq", models: ["llama-3.3-70b-versatile"] }],
      tts_models: { sarvam: ["bulbul:v3"] },
      stt_models: { sarvam: ["saaras:v3"], deepgram: ["nova-2-general"] },
      stt_providers: [{ id: "sarvam" }],
      tts_providers: [{ id: "sarvam", voices: ["kavya"] }],
      language_profiles: [],
      deepgram_configured: false,
    }),
    promptAssist: vi.fn().mockResolvedValue({ prompt: "refined", provider: "test" }),
    createAgent: vi.fn(),
    createAgentVersion: vi.fn(),
    updateAgent: vi.fn(),
    updateAgentVersion: vi.fn(),
    publishAgentVersion: vi.fn(),
    agent: vi.fn(),
    me: vi.fn().mockResolvedValue({ success: true, email: "test@example.com", role: "owner" }),
    saveConfig: vi.fn(),
    workspace: vi.fn().mockResolvedValue({ id: "workspace-1", name: "Personal", role: "owner", member_count: 1, settings: {} }),
    opsReadiness: vi.fn().mockResolvedValue({
      status: "needs_attention",
      ready_count: 7,
      total_count: 11,
      score: 64,
      checked_at: "2026-05-04T00:00:00Z",
      items: [],
    }),
  },
};
});

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
