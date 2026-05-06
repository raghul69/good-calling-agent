/**
 * Parse persisted CRM suffixes from call_logs.summary
 * ({@link backend/agent.py}: orch_lead=, disp=, xfer=)
 */

export type ParsedOrchestrationSummary = {
  baseSummary: string;
  orchLead: Record<string, unknown> | null;
  disposition: string | null;
  transferStatus: string | null;
};

function rsplitSep(str: string, sep: string): [string, string | null] {
  const idx = str.lastIndexOf(sep);
  if (idx < 0) return [str, null];
  return [str.slice(0, idx).trimEnd(), str.slice(idx + sep.length).trim()];
}

export function parseOrchestrationSummary(summary: unknown): ParsedOrchestrationSummary {
  const s = typeof summary === "string" ? summary.trim() : "";
  if (!s) {
    return { baseSummary: "", orchLead: null, disposition: null, transferStatus: null };
  }

  let [withoutXfer, xferRaw] = rsplitSep(s, " | xfer=");
  xferRaw = xferRaw?.trim() || null;

  let [withoutDisp, dispRaw] = rsplitSep(withoutXfer, " | disp=");
  dispRaw = dispRaw?.trim() || null;

  let basePart = withoutDisp.trim();
  let orchLead: Record<string, unknown> | null = null;
  const [maybeBase, orchJson] = rsplitSep(basePart, " | orch_lead=");
  if (orchJson != null) {
    basePart = maybeBase.trim();
    try {
      const parsed: unknown = JSON.parse(orchJson);
      orchLead =
        parsed && typeof parsed === "object" && !Array.isArray(parsed)
          ? (parsed as Record<string, unknown>)
          : null;
    } catch {
      orchLead = null;
    }
  }

  return {
    baseSummary: basePart,
    orchLead,
    disposition: dispRaw,
    transferStatus: xferRaw,
  };
}

/** Compact single-line transcript preview without breaking words mid-way if possible */
export function previewText(text: string | undefined | null, maxLen = 120): string {
  const raw = (text ?? "").trim();
  if (!raw || raw === "unavailable") return "";
  if (raw.length <= maxLen) return raw;
  return `${raw.slice(0, Math.max(0, maxLen - 1)).trim()}…`;
}

export function flattenedLeadPairs(lead: Record<string, unknown> | null | undefined): [string, string][] {
  if (!lead || typeof lead !== "object") return [];
  return Object.entries(lead).map(([k, v]) => [k, typeof v === "string" ? v : JSON.stringify(v)]);
}
