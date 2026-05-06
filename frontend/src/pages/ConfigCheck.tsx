import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  env,
  envIssueMessages,
  isApiConfigured,
  isPublicEnvValid,
  isSupabaseConfigured,
} from "../lib/env";
import { apiClientFetch } from "../lib/apiClient";

function mask(s: string, keep = 6): string {
  if (!s) return "(empty)";
  if (s.length <= keep * 2) return "•••";
  return `${s.slice(0, keep)}…${s.slice(-keep)}`;
}

export default function ConfigCheck() {
  const [apiOk, setApiOk] = useState<boolean | null>(null);
  const [apiErr, setApiErr] = useState("");

  useEffect(() => {
    if (!isApiConfigured) {
      setApiOk(false);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const res = await apiClientFetch("/health", { method: "GET" });
        if (!cancelled) setApiOk(res.ok);
      } catch (e: unknown) {
        if (!cancelled) {
          setApiOk(false);
          setApiErr(e instanceof Error ? e.message : String(e));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const rows = [
    { key: "NEXT_PUBLIC_SUPABASE_URL", set: Boolean(env.NEXT_PUBLIC_SUPABASE_URL), preview: mask(env.NEXT_PUBLIC_SUPABASE_URL, 12) },
    { key: "NEXT_PUBLIC_SUPABASE_ANON_KEY", set: Boolean(env.NEXT_PUBLIC_SUPABASE_ANON_KEY), preview: mask(env.NEXT_PUBLIC_SUPABASE_ANON_KEY) },
    { key: "NEXT_PUBLIC_API_URL", set: Boolean(env.NEXT_PUBLIC_API_URL), preview: mask(env.NEXT_PUBLIC_API_URL, 10) },
  ];

  return (
    <div className="min-h-screen bg-slate-950 px-4 py-10 text-slate-100">
      <div className="mx-auto max-w-lg rounded-xl border border-slate-700 bg-slate-900 p-6 shadow-xl">
        <h1 className="text-xl font-bold text-white">Configuration check</h1>
        <p className="mt-2 text-sm text-slate-400">
          Public env only (never prints secrets). Remove this route or restrict access if you expose non-dev deployments.
        </p>

        <ul className="mt-6 space-y-3 text-sm">
          {rows.map((r) => (
            <li key={r.key} className="flex flex-col rounded-lg border border-slate-700 bg-slate-950/80 px-3 py-2">
              <span className="font-mono text-xs text-slate-300">{r.key}</span>
              <span className={r.set ? "text-emerald-400" : "text-amber-400"}>{r.set ? "set" : "missing / invalid"}</span>
              <span className="text-xs text-slate-500">{r.preview}</span>
            </li>
          ))}
        </ul>

        <div className="mt-4 rounded-lg border border-slate-700 bg-slate-950/80 p-3 text-sm">
          <p>
            <span className="text-slate-400">Supabase ready:</span>{" "}
            <span className={isSupabaseConfigured ? "text-emerald-400" : "text-amber-400"}>{String(isSupabaseConfigured)}</span>
          </p>
          <p>
            <span className="text-slate-400">API URL ready:</span>{" "}
            <span className={isApiConfigured ? "text-emerald-400" : "text-amber-400"}>{String(isApiConfigured)}</span>
          </p>
          <p>
            <span className="text-slate-400">All public vars valid:</span>{" "}
            <span className={isPublicEnvValid ? "text-emerald-400" : "text-amber-400"}>{String(isPublicEnvValid)}</span>
          </p>
          <p>
            <span className="text-slate-400">GET /health:</span>{" "}
            <span className={apiOk === null ? "text-slate-500" : apiOk ? "text-emerald-400" : "text-amber-400"}>
              {apiOk === null ? "…" : apiOk ? "ok" : "failed"}
            </span>
          </p>
          {apiErr ? <p className="mt-2 text-xs text-red-400">{apiErr}</p> : null}
        </div>

        {envIssueMessages.length > 0 ? (
          <ul className="mt-4 list-disc space-y-1 pl-5 text-xs text-amber-200">
            {envIssueMessages.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        ) : null}

        <Link className="mt-6 inline-block text-sm font-semibold text-indigo-400 hover:text-indigo-300" to="/login">
          ← Back to login
        </Link>
      </div>
    </div>
  );
}
