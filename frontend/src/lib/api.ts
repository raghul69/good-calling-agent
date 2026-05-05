import { supabase } from "./supabase";
import { apiClientFetch, resolveApiUrl } from "./apiClient";
import { apiConnectionMessage, apiUnreachableMessage } from "./apiMessages";
import { env, isApiConfigured, isSupabaseConfigured } from "./env";

export { apiConnectionMessage, apiUnreachableMessage };
export { isApiConfigured } from "./env";

export const sessionExpiredMessage = "Your session expired. Please sign in again.";

/** Non-technical hint when browser/sip/livekit test fails */
export function formatCallTestFailureMessage(raw: unknown): string {
  const text = typeof raw === "string" ? raw : raw instanceof Error ? raw.message : String(raw);
  const short = text.length > 280 ? `${text.slice(0, 280)}…` : text;
  return `Something went wrong with the test call. ${short}`;
}

if (
  import.meta.env.DEV &&
  typeof window !== "undefined" &&
  isApiConfigured &&
  env.NEXT_PUBLIC_API_URL &&
  /^https:\/\/.*\.vercel\.app$/i.test(window.location.origin) &&
  !env.NEXT_PUBLIC_API_URL.includes("railway.app")
) {
  console.warn("[API][dev] NEXT_PUBLIC_API_URL should point at your Railway HTTPS host on production.");
}

export type AnalyticsSummary = {
  total_calls: number;
  answered_calls: number;
  failed_calls: number;
  total_bookings: number;
  avg_duration: number;
  average_duration: number;
  total_minutes: number;
  estimated_ai_cost: number;
  booking_rate: number;
};

export type CallNowResponse = {
  call_id: string;
  dispatch_id?: string;
  room_name: string;
  roomName?: string;
  status: string;
  phone_number: string;
  agent_id?: string | null;
  agent_version_id?: string | null;
  published_agent_uuid?: string | null;
  token?: string;
  url?: string;
  started_at?: string;
};

export type LiveKitBrowserTestResponse = {
  call_id?: string;
  dispatch_id?: string;
  roomName: string;
  room: string;
  token: string;
  url: string;
  status: string;
  started_at: string;
  agent_id?: string | null;
  agent_version_id?: string | null;
  published_agent_uuid?: string | null;
};

export type SipHealthResponse = {
  ok: boolean;
  trunk_configured: boolean;
  livekit_configured: boolean;
  sip_trunk_id?: string | null;
  livekit: Record<string, unknown>;
};

export type LiveKitHealthResponse = {
  ok: boolean;
  livekit: Record<string, unknown>;
  room_count: number | null;
  api_reachable: boolean;
  error?: string;
};

export type SipTestCallResponse = {
  status: string;
  room_name: string;
  phone_number_masked: string;
  sip_status: string;
  dispatch_id?: string | null;
  call_id?: string | number | null;
  agent_id?: string | null;
  agent_version_id?: string | null;
  published_agent_uuid?: string | null;
  started_at?: string;
};

export type CurrentUser = {
  success: boolean;
  user_id?: string;
  email?: string;
  role?: string;
  roles?: string[];
  workspace_id?: string | null;
  workspace_created?: boolean;
};

export type WorkspaceSummary = {
  id: string | null;
  name: string;
  role: string;
  member_count: number;
  settings: Record<string, unknown>;
};

export type BillingSummary = {
  plan: string;
  status: string;
  included_minutes: number;
  used_minutes: number;
  overage_minutes: number;
  estimated_ai_cost: number;
  next_invoice_estimate: number;
  stripe_configured?: boolean;
  stripe_customer_id?: string;
  stripe_subscription_id?: string;
  current_period_end?: number;
  cancel_at_period_end?: boolean;
};

export type Campaign = {
  id?: string;
  name: string;
  status?: string;
  total_calls?: number;
  completed_calls?: number;
  created_at?: string;
};

export type PromptAssistAction =
  | "improve"
  | "shorten"
  | "rewrite_professional"
  | "optimize_sales"
  | "optimize_support"
  | "optimize_real_estate";

export type PromptAssistRequest = {
  current_prompt: string;
  action: PromptAssistAction;
  language_profile?: string;
  language_profile_label?: string;
  tone?: string;
  business_type?: string;
};

export type PromptAssistResponse = {
  prompt: string;
  provider: string;
  model: string;
};

export type AgentRow = {
  id?: string;
  published_agent_uuid?: string | null;
  name?: string;
  status?: string;
  description?: string;
  visibility?: string;
  default_language?: string;
  phone?: string;
  active_version_id?: string;
  active_version?: {
    id?: string;
    version?: number;
    status?: string;
    welcome_message?: string;
    system_prompt?: string;
    multilingual_prompts?: Record<string, string>;
    prompt_variables?: Array<Record<string, unknown>>;
    llm_config?: Record<string, unknown>;
    audio_config?: Record<string, unknown>;
    engine_config?: Record<string, unknown>;
    call_config?: Record<string, unknown>;
    tools_config?: Array<Record<string, unknown>>;
    analytics_config?: Record<string, unknown>;
    published_at?: string | null;
  };
  versions?: NonNullable<AgentRow["active_version"]>[];
  config?: {
    name?: string;
    phone?: string;
    welcomeMessage?: string;
    first_line?: string;
    prompt?: string;
    agent_instructions?: string;
    inbound_number_id?: string;
    inbound_assign_enabled?: boolean;
  };
};

export type CallLogRow = {
  id?: string | number;
  created_at?: string;
  started_at?: string | null;
  /** E.164 or raw */
  phone?: string | null;
  phone_number?: string | null;
  caller_name?: string | null;
  duration?: number | null;
  transcript?: string | null;
  summary?: string | null;
  status?: string | null;
  room_name?: string | null;
  failure_reason?: string | null;
  manual_disposition?: string | null;
  sentiment?: string | null;
  agent_id?: string | null;
  agent_version_id?: string | null;
  published_agent_uuid?: string | null;
  user_id?: string | null;
  workspace_id?: string | null;
};

export type CallsListParams = {
  limit?: number;
  offset?: number;
  /** ISO timestamp lower bound inclusive */
  created_at_gte?: string;
  created_at_lte?: string;
  status?: string;
  agent_id?: string;
  phone_search?: string;
  failed_only?: boolean;
  transferred_only?: boolean;
  disposition?: string;
};

export type CallsListResponse = {
  items: CallLogRow[];
  limit: number;
  offset: number;
  has_more: boolean;
};

export type AgentVersionPayload = {
  welcome_message?: string;
  system_prompt?: string;
  multilingual_prompts?: Record<string, string>;
  prompt_variables?: Array<Record<string, unknown>>;
  llm_config?: Record<string, unknown>;
  audio_config?: Record<string, unknown>;
  engine_config?: Record<string, unknown>;
  call_config?: Record<string, unknown>;
  tools_config?: Array<Record<string, unknown>>;
  analytics_config?: Record<string, unknown>;
  status?: string;
};

export type AgentPayload = AgentVersionPayload & {
  name?: string;
  description?: string;
  status?: string;
  visibility?: string;
  default_language?: string;
  config?: Record<string, unknown>;
};

export type AgentPublishResponse = {
  success: boolean;
  agent: AgentRow;
  version: NonNullable<AgentRow["active_version"]>;
  published_agent_uuid?: string;
};

/** GET /api/providers/options — agent builder presets */
export type ProviderOptionsResponse = {
  language_profiles?: Array<{
    id: string;
    label?: string;
    tts_language?: string;
    tts_voice?: string;
    instruction?: string;
  }>;
  llm_providers?: Array<{ id: string; label?: string; models?: string[] }>;
  tts_providers?: Array<{ id: string; label?: string; voices?: string[] }>;
  stt_providers?: Array<{ id: string; label?: string; languages?: string[] }>;
  tts_models?: Record<string, string[]>;
  stt_models?: Record<string, string[]>;
  engine_defaults?: Record<string, number>;
  deepgram_configured?: boolean;
};

export type ContactRow = {
  caller_name?: string;
  phone?: string;
  full_name?: string;
  phone_e164?: string;
  total_calls?: number;
  id?: string;
  source?: string;
  tags?: unknown;
};

export type OpsReadinessItem = {
  key: string;
  label: string;
  ready: boolean;
  detail: string;
  action: string;
};

export type OpsReadiness = {
  status: "ready" | "needs_attention";
  ready_count: number;
  total_count: number;
  score: number;
  checked_at: string;
  items: OpsReadinessItem[];
};

export function apiUrl(path: string): string {
  if (!path.startsWith("/")) return path;
  if (!isApiConfigured) {
    throw new Error(apiConnectionMessage);
  }
  return resolveApiUrl(path);
}

export async function getAccessToken(): Promise<string> {
  if (!isSupabaseConfigured) return "";
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token || "";
}

export async function signOut(): Promise<void> {
  if (!isSupabaseConfigured) return;
  await supabase.auth.signOut();
}

export const SESSION_EXPIRED_EVENT = "jettone:session-expired";

function buildQueryString(params: Record<string, string | number | boolean | undefined | null>): string {
  const u = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    if (typeof v === "boolean") {
      u.set(k, v ? "true" : "false");
      continue;
    }
    u.set(k, String(v));
  }
  const s = u.toString();
  return s ? `?${s}` : "";
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (!isApiConfigured) {
    throw new Error(apiConnectionMessage);
  }
  const token = await getAccessToken();
  const headers = new Headers(init.headers || {});
  headers.set("Accept", "application/json");
  if (!(init.body instanceof FormData) && init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let res: Response;
  try {
    res = await apiClientFetch(path, {
      ...init,
      headers,
    });
  } catch {
    throw new Error(apiUnreachableMessage);
  }

  const contentType = res.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await res.json() : await res.text();

  if (path.startsWith("/api/") && !contentType.includes("application/json")) {
    throw new Error(apiUnreachableMessage);
  }

  if (!res.ok) {
    if (res.status === 401) {
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent(SESSION_EXPIRED_EVENT, { detail: { message: sessionExpiredMessage } }));
      }
      if (isSupabaseConfigured) await supabase.auth.signOut();
    }
    const payload = data as {
      error?: { message?: string };
      detail?: string;
      message?: string;
    };
    const message = typeof data === "object" && data
      ? String(
          payload.error?.message ||
          payload.detail ||
          payload.message ||
          `API request failed: ${res.status}`,
        )
      : `API request failed: ${res.status}`;
    throw new Error(message);
  }

  return data as T;
}

export async function fetchCallDetail(call_log_id: string | number): Promise<CallLogRow> {
  const encoded = encodeURIComponent(String(call_log_id));
  try {
    return await apiFetch<CallLogRow>(`/api/calls/${encoded}`);
  } catch {
    return await apiFetch<CallLogRow>(`/api/logs/${encoded}`);
  }
}

export async function apiFetchWithFallback<T>(paths: string[], fallback: T): Promise<T> {
  for (const path of paths) {
    try {
      return await apiFetch<T>(path);
    } catch (error) {
      if (import.meta.env.DEV && path === paths[paths.length - 1]) {
        console.warn(`API fallback used after ${paths.join(", ")} failed`, error);
      }
    }
  }
  return fallback;
}

export const api = {
  health: () => apiFetch<Record<string, unknown>>("/api/health"),
  sipHealth: () => apiFetch<SipHealthResponse>("/api/sip/health"),
  livekitHealth: () => apiFetch<LiveKitHealthResponse>("/api/livekit/health"),
  me: () => apiFetch<CurrentUser>("/api/auth/me"),
  workspace: () => apiFetch<WorkspaceSummary>("/api/workspace"),
  billing: () => apiFetch<BillingSummary>("/api/billing"),
  createCheckout: (price_id?: string) =>
    apiFetch<{ url: string; id: string }>("/api/billing/checkout", {
      method: "POST",
      body: JSON.stringify({ price_id }),
    }),
  billingPortal: () =>
    apiFetch<{ url: string }>("/api/billing/portal", {
      method: "POST",
    }),
  opsReadiness: () => apiFetchWithFallback<OpsReadiness | null>(["/api/ops/readiness"], null),
  agents: () => apiFetchWithFallback<AgentRow[]>(["/api/agents"], []),
  agent: (agent_id: string) => apiFetch<AgentRow>(`/api/agents/${agent_id}`),
  createAgent: (payload: AgentPayload) =>
    apiFetch<AgentRow>("/api/agents", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateAgent: (agent_id: string, payload: AgentPayload) =>
    apiFetch<AgentRow>(`/api/agents/${agent_id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  createAgentVersion: (agent_id: string, payload: AgentVersionPayload) =>
    apiFetch<NonNullable<AgentRow["active_version"]>>(`/api/agents/${agent_id}/versions`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateAgentVersion: (agent_id: string, version_id: string, payload: AgentVersionPayload) =>
    apiFetch<NonNullable<AgentRow["active_version"]>>(`/api/agents/${agent_id}/versions/${version_id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  publishAgentVersion: (agent_id: string, version_id: string) =>
    apiFetch<AgentPublishResponse>(`/api/agents/${agent_id}/versions/${version_id}/publish`, {
      method: "POST",
    }),
  callsList: (opts: CallsListParams = {}) =>
    apiFetchWithFallback<CallsListResponse>(
      [`/api/calls${buildQueryString(opts)}`, `/api/logs${buildQueryString(opts)}`],
      { items: [], limit: opts.limit ?? 25, offset: opts.offset ?? 0, has_more: false },
    ),
  callDetail: (call_log_id: string | number) => fetchCallDetail(call_log_id),
  campaigns: () => apiFetchWithFallback<Campaign[]>(["/api/campaigns"], []),
  analytics: () =>
    apiFetchWithFallback<AnalyticsSummary>(["/api/analytics", "/api/stats"], {
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
  contacts: () => apiFetchWithFallback<ContactRow[]>(["/api/contacts"], []),
  promptAssist: (payload: PromptAssistRequest) =>
    apiFetch<PromptAssistResponse>("/api/agents/prompt-assist", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  providerOptions: () => apiFetch<ProviderOptionsResponse>("/api/providers/options"),
  config: () => apiFetch<Record<string, unknown>>("/api/config"),
  saveConfig: (config: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/api/config", {
      method: "POST",
      body: JSON.stringify(config),
    }),
  demoToken: () => apiFetch<{ token?: string; room?: string; url?: string; error?: string }>("/api/demo-token"),
  livekitToken: (room_name?: string, agent_id?: string) =>
    apiFetch<{ roomName: string; room: string; token: string; url: string }>("/api/livekit/token", {
      method: "POST",
      body: JSON.stringify({ room_name, agent_id }),
    }),
  browserTest: (published_agent_uuid?: string) =>
    apiFetch<LiveKitBrowserTestResponse>("/api/calls/browser-test", {
      method: "POST",
      body: JSON.stringify({ published_agent_uuid }),
    }),
  outboundCall: (phone_number: string, published_agent_uuid?: string) =>
    apiFetch<CallNowResponse>("/api/calls/outbound", {
      method: "POST",
      body: JSON.stringify({ phone_number, published_agent_uuid }),
    }),
  sipTestCall: (phone_number: string, published_agent_uuid?: string) =>
    apiFetch<SipTestCallResponse>("/api/sip/test-call", {
      method: "POST",
      body: JSON.stringify({ phone_number, published_agent_uuid }),
    }),
  callNow: (phone_number: string, agent_id?: string) =>
    apiFetch<CallNowResponse>("/call", {
      method: "POST",
      body: JSON.stringify({ phone_number, agent_id }),
    }),
};
