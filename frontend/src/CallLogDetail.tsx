import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from './lib/api';
import type { CallLogRow } from './lib/api';
import { flattenedLeadPairs, parseOrchestrationSummary } from './lib/callCrmSummary';
import { InlineBanner, PageLoading, Spinner } from './components/UiFeedback';

function getErrorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

export function CallLogLegend() {
  return (
    <p className="text-xs text-slate-500">
      Summary CRM tokens:{' '}
      <code className="rounded bg-slate-100 px-1 py-0.5">orch_lead=…</code>,{' '}
      <code className="rounded bg-slate-100 px-1 py-0.5">disp=…</code>,{' '}
      <code className="rounded bg-slate-100 px-1 py-0.5">xfer=…</code>
    </p>
  );
}

export default function CallLogDetail() {
  const { callId } = useParams<{ callId: string }>();
  const [row, setRow] = useState<CallLogRow | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    if (!callId) {
      setLoading(false);
      setError('Missing call id.');
      return;
    }
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError('');
      try {
        const data = await api.callDetail(callId);
        if (!cancelled) setRow(data);
      } catch (e: unknown) {
        if (!cancelled) setError(getErrorMessage(e, 'Could not load this call.'));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [callId, refreshKey]);

  const parsed = typeof row?.summary === 'string' ? parseOrchestrationSummary(row.summary) : parseOrchestrationSummary('');
  const disp = (typeof row?.manual_disposition === 'string' ? row.manual_disposition : '').trim() || parsed.disposition || '';
  const xfer = parsed.transferStatus;
  const transcript = typeof row?.transcript === 'string' ? row.transcript.trim() : '';

  if (!callId) {
    return (
      <CallLogShell>
        <InlineBanner tone="error">Invalid call URL.</InlineBanner>
      </CallLogShell>
    );
  }

  if (loading && !row) {
    return (
      <CallLogShell>
        <PageLoading message="Loading call…" />
      </CallLogShell>
    );
  }

  if (error && !row) {
    return (
      <CallLogShell>
        <InlineBanner tone="error" title="Call unavailable">
          {error}
        </InlineBanner>
        <button
          type="button"
          onClick={() => setRefreshKey((k) => k + 1)}
          className="mt-4 inline-flex min-h-10 items-center gap-2 rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-900 shadow-sm hover:bg-slate-50"
        >
          Retry
        </button>
      </CallLogShell>
    );
  }

  return (
    <CallLogShell>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <CallLogLegend />
        <button
          type="button"
          onClick={() => setRefreshKey((k) => k + 1)}
          className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-800 shadow-sm hover:bg-slate-50"
          disabled={loading}
        >
          {loading ? <Spinner className="h-4 w-4" label="Refreshing" /> : null} Retry
        </button>
      </div>
      {error ? (
        <div className="mb-4">
          <InlineBanner tone="warning" title="Reload issue">
            {error}
          </InlineBanner>
        </div>
      ) : null}

      <MetadataGrid row={row!} disposition={disp} transferStatus={xfer ?? '—'} />

      <section className="mt-6 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="text-sm font-bold text-slate-950">Transcript</h2>
        <div className="mt-3 max-h-[min(70vh,720px)] overflow-auto rounded-md bg-slate-50 p-4 text-sm text-slate-800">
          {transcript && transcript !== 'unavailable' ? (
            <pre className="whitespace-pre-wrap font-sans">{transcript}</pre>
          ) : (
            <p className="text-slate-500">Transcript unavailable for this call.</p>
          )}
        </div>
      </section>

      <section className="mt-6 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="text-sm font-bold text-slate-950">orch_lead (extracted)</h2>
        {parsed.orchLead && Object.keys(parsed.orchLead).length > 0 ? (
          <ul className="mt-3 space-y-1 text-sm text-slate-700">
            {flattenedLeadPairs(parsed.orchLead).map(([k, v]) => (
              <li key={k} className="break-words border-b border-slate-100 pb-1 last:border-0">
                <span className="font-semibold text-slate-500">{k}:</span> {v || '—'}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm text-slate-500">No orch_lead payload captured (empty or malformed).</p>
        )}
        <details className="mt-4 rounded-md border border-slate-100 bg-slate-50 p-3">
          <summary className="cursor-pointer text-sm font-semibold text-slate-800">Pretty JSON</summary>
          <pre className="mt-2 overflow-x-auto whitespace-pre-wrap text-xs text-slate-700">
            {parsed.orchLead ? JSON.stringify(parsed.orchLead, null, 2) : 'null'}
          </pre>
        </details>
      </section>

      <section className="mt-6 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="text-sm font-bold text-slate-950">Summary for log</h2>
        <p className="mt-2 whitespace-pre-wrap break-words text-sm text-slate-700">
          {typeof row!.summary === 'string' ? row!.summary : '—'}
        </p>
      </section>

      <details className="mt-6 rounded-lg border border-dashed border-slate-300 bg-slate-50 p-4">
        <summary className="cursor-pointer text-sm font-bold text-slate-800">Raw row (debug)</summary>
        <pre className="mt-3 max-h-[50vh] overflow-auto text-xs text-slate-700">{JSON.stringify(row, null, 2)}</pre>
      </details>
    </CallLogShell>
  );
}

function CallLogShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-full min-w-0 bg-slate-50 px-4 py-6 text-slate-950 sm:px-6 md:p-8">
      <div className="mb-6">
        <Link to="/logs" className="text-sm font-semibold text-blue-600 hover:text-blue-800">
          ← Back to call history
        </Link>
        <h1 className="mt-3 text-2xl font-black tracking-tight sm:text-3xl">Call detail</h1>
        <p className="mt-2 text-sm text-slate-500">Transcript, CRM snapshot, and metadata for this call.</p>
      </div>
      {children}
    </div>
  );
}

function MetadataGrid({
  row,
  disposition,
  transferStatus,
}: {
  row: CallLogRow;
  disposition: string;
  transferStatus: string;
}) {
  const parsed = typeof row.summary === 'string' ? parseOrchestrationSummary(row.summary) : parseOrchestrationSummary('');
  const effectiveDisp =
    disposition || (typeof row.manual_disposition === 'string' && row.manual_disposition.trim()) || parsed.disposition || '—';

  const items: [string, string][] = [
    ['caller_name', String(row.caller_name ?? '—')],
    ['phone_number', String(row.phone_number ?? row.phone ?? '—')],
    ['duration_sec', row.duration !== undefined && row.duration !== null ? String(row.duration) : '—'],
    ['created_at', String(row.created_at ?? '—')],
    ['started_at', String(row.started_at ?? '—')],
    ['status', String(row.status ?? '—')],
    ['disposition', String(effectiveDisp)],
    ['transfer_status', transferStatus || '—'],
    ['agent_id', String(row.agent_id ?? '—')],
    ['room_name', String(row.room_name ?? '—')],
    ['failure_reason', String(row.failure_reason ?? '—')],
  ];

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="grid gap-3 text-sm md:grid-cols-2">
        {items.map(([label, val]) => (
          <div key={label} className="break-words">
            <span className="font-semibold text-slate-500">{label}:</span>{' '}
            <span className="text-slate-900">{val}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
