import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api, type AgentRow, type CallsListParams, type CallsListResponse, type CallLogRow } from './lib/api';
import { parseOrchestrationSummary, previewText } from './lib/callCrmSummary';
import { EmptyWell, InlineBanner, PageLoading } from './components/UiFeedback';
import { ShellButton } from './components/ShellButton';
import { CallLogLegend } from './CallLogDetail';

const PAGE_LIMIT_DEFAULT = 25;

function getErrorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

function dispositionLabel(row: CallLogRow) {
  const manual = typeof row.manual_disposition === 'string' ? row.manual_disposition.trim() : '';
  if (manual) return manual;
  const s = typeof row.summary === 'string' ? row.summary : '';
  return parseOrchestrationSummary(s).disposition || '—';
}

function transferLabel(row: CallLogRow) {
  const s = typeof row.summary === 'string' ? row.summary : '';
  const p = parseOrchestrationSummary(s);
  return p.transferStatus || '—';
}

function displayPhone(row: CallLogRow) {
  return String(row.phone_number ?? row.phone ?? '').trim() || '—';
}

function displayName(row: CallLogRow) {
  return String(row.caller_name ?? '').trim() || '—';
}

function isoEndOfUtcDay(dateYmd: string): string | undefined {
  if (!dateYmd) return undefined;
  return `${dateYmd}T23:59:59.999Z`;
}

function isoStartUtcDay(dateYmd: string): string | undefined {
  if (!dateYmd) return undefined;
  return `${dateYmd}T00:00:00.000Z`;
}

function exportCallsCsvCurrentPage(rows: CallLogRow[]) {
  const header = [
    'caller_name',
    'phone_number',
    'disposition',
    'transfer_status',
    'duration_sec',
    'status',
    'created_at',
    'agent_id',
    'summary_preview',
  ];
  const lines = rows.map((row) => {
    const s = typeof row.summary === 'string' ? row.summary : '';
    const parsed = parseOrchestrationSummary(s);
    const vals = [
      displayName(row).replace(/"/g, '""'),
      displayPhone(row).replace(/"/g, '""'),
      dispositionLabel(row).replace(/"/g, '""'),
      (parsed.transferStatus || '').replace(/"/g, '""'),
      String(row.duration ?? ''),
      String(row.status ?? ''),
      String(row.created_at ?? ''),
      String(row.agent_id ?? ''),
      previewText(s, 400).replace(/"/g, '""'),
    ];
    return vals.map((v) => `"${v}"`).join(',');
  });
  const blob = new Blob([['\ufeff', header.join(','), '\n', lines.join('\n')].join('')], {
    type: 'text/csv;charset=utf-8',
  });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `call-logs-export-${Date.now()}.csv`;
  a.click();
  URL.revokeObjectURL(a.href);
}

function CallsTableDesktop({ rows, agentsById }: { rows: CallLogRow[]; agentsById: Record<string, string> }) {
  return (
    <div className="hidden overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm md:block">
      <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
        <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-3">When</th>
            <th className="px-4 py-3">Caller</th>
            <th className="px-4 py-3">Phone</th>
            <th className="px-4 py-3">Disp.</th>
            <th className="px-4 py-3">Xfer</th>
            <th className="px-4 py-3">Dur</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Agent</th>
            <th className="px-4 py-3">Summary</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((row, index) => {
            const key = row.id !== undefined && row.id !== null ? String(row.id) : `idx-${index}`;
            const idForLink =
              row.id !== undefined && row.id !== null ? encodeURIComponent(String(row.id)) : null;
            const agentLabel = row.agent_id ? agentsById[String(row.agent_id)] ?? row.agent_id : '—';
            const summary = typeof row.summary === 'string' ? row.summary : '';
            return (
              <tr key={key} className="bg-white hover:bg-slate-50/80">
                <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-600">{row.created_at || '—'}</td>
                <td className="max-w-[10rem] truncate px-4 py-3 font-medium text-slate-900">{displayName(row)}</td>
                <td className="max-w-[8rem] truncate px-4 py-3 text-slate-700">{displayPhone(row)}</td>
                <td className="max-w-[8rem] truncate px-4 py-3 text-slate-700">{dispositionLabel(row)}</td>
                <td className="max-w-[8rem] truncate px-4 py-3 text-slate-700">{transferLabel(row)}</td>
                <td className="whitespace-nowrap px-4 py-3 text-slate-700">{row.duration ?? '—'}</td>
                <td className="max-w-[6rem] truncate px-4 py-3 text-xs text-slate-600">{row.status || '—'}</td>
                <td className="max-w-[8rem] truncate px-4 py-3 text-xs text-slate-600">{agentLabel}</td>
                <td className="max-w-xs px-4 py-3 text-xs text-slate-600">
                  {idForLink ? (
                    <Link className="font-semibold text-blue-600 hover:text-blue-800" to={`/logs/${idForLink}`}>
                      {previewText(summary, 120)}
                    </Link>
                  ) : (
                    previewText(summary, 120)
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function CallsCardsMobile({ rows, agentsById }: { rows: CallLogRow[]; agentsById: Record<string, string> }) {
  return (
    <div className="space-y-3 md:hidden">
      {rows.map((row, index) => {
        const key = row.id !== undefined && row.id !== null ? String(row.id) : `idx-${index}`;
        const idForLink =
          row.id !== undefined && row.id !== null ? encodeURIComponent(String(row.id)) : null;
        const summary = typeof row.summary === 'string' ? row.summary : '';
        const agentLabel = row.agent_id ? agentsById[String(row.agent_id)] ?? row.agent_id : '—';
        return (
          <div key={key} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="text-xs text-slate-500">{row.created_at || '—'}</div>
            <div className="mt-1 font-semibold text-slate-950">{displayName(row)}</div>
            <div className="text-sm text-slate-600">{displayPhone(row)}</div>
            <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-600">
              <span className="rounded-full bg-slate-100 px-2 py-0.5">{dispositionLabel(row)}</span>
              <span className="rounded-full bg-slate-100 px-2 py-0.5">{transferLabel(row)}</span>
              <span className="rounded-full bg-slate-100 px-2 py-0.5">{row.status || 'unknown'}</span>
            </div>
            <p className="mt-2 line-clamp-3 text-xs text-slate-600">{previewText(summary, 220)}</p>
            <p className="mt-2 text-[11px] text-slate-500">Agent: {agentLabel}</p>
            {idForLink ? (
              <Link
                className="mt-3 inline-flex text-sm font-semibold text-blue-600 hover:text-blue-800"
                to={`/logs/${idForLink}`}
              >
                Open detail →
              </Link>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

function FiltersBar(props: {
  searchParams: URLSearchParams;
  phoneDraft: string;
  onPhoneInput: (v: string) => void;
  onApplyDates: (from: string, to: string) => void;
  onDisposition: (v: string) => void;
  onFailed: (checked: boolean) => void;
  onTransferred: (checked: boolean) => void;
  onAgent: (v: string) => void;
  agentsById: Record<string, string>;
  onReload: () => void;
}) {
  const sp = props.searchParams;
  const [draftFrom, setDraftFrom] = useState(sp.get('from') || '');
  const [draftTo, setDraftTo] = useState(sp.get('to') || '');

  const dateBoundsKey = `${sp.get('from') ?? ''}|${sp.get('to') ?? ''}`;
  useEffect(() => {
    const p = props.searchParams;
    setDraftFrom(p.get('from') || '');
    setDraftTo(p.get('to') || '');
  }, [dateBoundsKey]);

  return (
    <div className="mb-6 space-y-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap gap-4">
        <label className="block text-xs font-semibold text-slate-700">
          From (UTC day)
          <input
            type="date"
            value={draftFrom}
            onChange={(e) => setDraftFrom(e.target.value)}
            className="mt-1 block rounded-md border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400"
          />
        </label>
        <label className="block text-xs font-semibold text-slate-700">
          To (UTC day)
          <input
            type="date"
            value={draftTo}
            onChange={(e) => setDraftTo(e.target.value)}
            className="mt-1 block rounded-md border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400"
          />
        </label>
        <div className="flex items-end">
          <ShellButton primary onClick={() => props.onApplyDates(draftFrom, draftTo)}>
            Apply dates
          </ShellButton>
        </div>
        <label className="flex min-h-10 flex-1 min-w-[12rem] flex-col text-xs font-semibold text-slate-700 md:max-w-xs">
          Phone search
          <input
            value={props.phoneDraft}
            onChange={(e) => props.onPhoneInput(e.target.value)}
            placeholder="+91… fragment"
            className="mt-1 rounded-md border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400"
          />
        </label>
      </div>
      <div className="flex flex-wrap gap-4">
        <label className="text-xs font-semibold text-slate-700">
          Disposition
          <select
            className="mt-1 block min-w-[180px] rounded-md border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400"
            value={sp.get('disposition') || ''}
            onChange={(e) => props.onDisposition(e.target.value)}
          >
            <option value="">Any</option>
            <option value="booking_confirmed">booking_confirmed</option>
            <option value="booking_failed">booking_failed</option>
            <option value="completed">completed</option>
            <option value="interested">interested</option>
            <option value="not_interested">not_interested</option>
            <option value="follow_up">follow_up</option>
            <option value="transferred">transferred</option>
            <option value="failed">failed</option>
            <option value="unknown">unknown</option>
          </select>
        </label>
        <label className="text-xs font-semibold text-slate-700">
          Agent
          <select
            className="mt-1 block min-w-[200px] rounded-md border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400"
            value={sp.get('agent_id') || ''}
            onChange={(e) => props.onAgent(e.target.value)}
          >
            <option value="">Any</option>
            {Object.entries(props.agentsById).map(([id, name]) => (
              <option key={id} value={id}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <label className="flex cursor-pointer items-center gap-2 pt-7 text-sm text-slate-800">
          <input type="checkbox" checked={sp.get('failed_only') === '1'} onChange={(e) => props.onFailed(e.target.checked)} />
          Failed only
        </label>
        <label className="flex cursor-pointer items-center gap-2 pt-7 text-sm text-slate-800">
          <input
            type="checkbox"
            checked={sp.get('transferred_only') === '1'}
            onChange={(e) => props.onTransferred(e.target.checked)}
          />
          Transferred (xfer ok / requested)
        </label>
        <div className="flex flex-1 items-end justify-end">
          <ShellButton onClick={props.onReload}>Reload</ShellButton>
        </div>
      </div>
    </div>
  );
}

/** Call history: filters in URL, pagination, CSV (current page), links to `/logs/:id`. */
export default function CallLogsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [data, setData] = useState<CallsListResponse | null>(null);
  const [agentsById, setAgentsById] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [phoneDraft, setPhoneDraft] = useState(() => searchParams.get('phone_search') || '');
  const [refreshKey, setRefreshKey] = useState(0);

  const phoneTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setPhoneDraft(searchParams.get('phone_search') || '');
  }, [searchParams]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const agents = await api.agents();
        const map: Record<string, string> = {};
        (agents || []).forEach((a: AgentRow) => {
          if (a.id) map[String(a.id)] = a.name || String(a.id);
        });
        if (!cancelled) setAgentsById(map);
      } catch {
        if (!cancelled) setAgentsById({});
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const queryFromUrl = useCallback((): CallsListParams => {
    const rawOff = searchParams.get('offset');
    const rawLim = searchParams.get('limit');
    const offset = rawOff !== null ? Number.parseInt(rawOff, 10) : 0;
    const limit = rawLim !== null ? Number.parseInt(rawLim, 10) : PAGE_LIMIT_DEFAULT;
    return {
      limit: Number.isFinite(limit) ? Math.min(100, Math.max(1, limit)) : PAGE_LIMIT_DEFAULT,
      offset: Number.isFinite(offset) && offset >= 0 ? offset : 0,
      created_at_gte: searchParams.get('from') ? isoStartUtcDay(searchParams.get('from')!) : undefined,
      created_at_lte: searchParams.get('to') ? isoEndOfUtcDay(searchParams.get('to')!) : undefined,
      status: searchParams.get('status') || undefined,
      agent_id: searchParams.get('agent_id') || undefined,
      phone_search: searchParams.get('phone_search') || undefined,
      failed_only: searchParams.get('failed_only') === '1',
      transferred_only: searchParams.get('transferred_only') === '1',
      disposition: searchParams.get('disposition') || undefined,
    };
  }, [searchParams]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError('');
      try {
        const res = await api.callsList(queryFromUrl());
        if (!cancelled) setData(res);
      } catch (e: unknown) {
        if (!cancelled) {
          setData(null);
          setError(getErrorMessage(e, 'Failed to load call logs.'));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [searchParams, queryFromUrl, refreshKey]);

  const rows = data?.items ?? [];
  const hasMore = Boolean(data?.has_more);
  const offset = data?.offset ?? 0;
  const limit = data?.limit ?? PAGE_LIMIT_DEFAULT;

  const setParams = useCallback(
    (patch: Record<string, string | null>) => {
      const next = new URLSearchParams(searchParams);
      for (const [k, v] of Object.entries(patch)) {
        if (v === null || v === '') next.delete(k);
        else next.set(k, v);
      }
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  const onPhoneInput = useCallback((value: string) => {
    setPhoneDraft(value);
    if (phoneTimer.current) clearTimeout(phoneTimer.current);
    phoneTimer.current = setTimeout(() => {
      setParams({
        phone_search: value.trim() || null,
        offset: null,
      });
    }, 350);
  }, [setParams]);

  return (
    <div className="min-h-full min-w-0 bg-slate-50 px-4 py-6 text-slate-950 sm:px-6 md:p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-black tracking-tight sm:text-3xl">Call History</h1>
        <p className="mt-2 text-sm text-slate-500">
          Filters sync to the URL. Date inputs are interpreted as UTC day bounds. CSV exports the current page only (up to the
          active limit).
        </p>
        <div className="mt-3">
          <CallLogLegend />
        </div>
      </div>

      <FiltersBar
        searchParams={searchParams}
        phoneDraft={phoneDraft}
        onPhoneInput={onPhoneInput}
        onApplyDates={(from, to) =>
          setParams({
            from: from || null,
            to: to || null,
            offset: null,
          })
        }
        onDisposition={(v) => setParams({ disposition: v || null, offset: null })}
        onFailed={(checked) => setParams({ failed_only: checked ? '1' : null, offset: null })}
        onTransferred={(checked) => setParams({ transferred_only: checked ? '1' : null, offset: null })}
        onAgent={(v) => setParams({ agent_id: v || null, offset: null })}
        agentsById={agentsById}
        onReload={() => setRefreshKey((k) => k + 1)}
      />

      {loading ? (
        <PageLoading message="Loading call logs…" />
      ) : error ? (
        <>
          <InlineBanner tone="error" title="Call logs unavailable">
            {error}
          </InlineBanner>
          <ShellButton primary className="mt-4" onClick={() => setRefreshKey((k) => k + 1)}>
            Retry
          </ShellButton>
        </>
      ) : rows.length === 0 ? (
        <EmptyWell
          title="No matching calls"
          description="Adjust filters or place a test call from Agents — logs appear once your Railway worker saves them."
        >
          <Link to="/agents">
            <ShellButton primary>Go to Agents</ShellButton>
          </Link>
        </EmptyWell>
      ) : (
        <>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-slate-600">
              Showing <span className="font-semibold">{rows.length}</span> row{rows.length === 1 ? '' : 's'}
              {hasMore ? ' (more on next page).' : '.'}
            </p>
            <div className="flex flex-wrap gap-2">
              <ShellButton onClick={() => exportCallsCsvCurrentPage(rows)}>Export CSV</ShellButton>
              <ShellButton
                disabled={offset === 0}
                onClick={() => setParams({ offset: String(Math.max(0, offset - limit)) })}
              >
                Previous
              </ShellButton>
              <ShellButton disabled={!hasMore} onClick={() => setParams({ offset: String(offset + limit) })}>
                Next
              </ShellButton>
            </div>
          </div>
          <CallsTableDesktop rows={rows} agentsById={agentsById} />
          <CallsCardsMobile rows={rows} agentsById={agentsById} />
        </>
      )}
    </div>
  );
}
