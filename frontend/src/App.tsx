import { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Link, useLocation, Navigate, useNavigate } from 'react-router-dom';
import { ChartLineUp, PhoneCall, Users, Gear, TerminalWindow } from '@phosphor-icons/react';
import VoiceTester from './VoiceTester';
import TerminalPage from './Terminal';
import Login from './Login';
import { authFetch, clearAccessToken, getAccessToken } from './auth';
import './App.css';

type HealthPayload = {
  supabase_configured?: boolean;
  livekit_configured?: boolean;
  service_role_key_present?: boolean;
  status?: string;
};

function IntegrationPills({ health }: { health: HealthPayload | null }) {
  if (!health) {
    return (
      <div className="flex flex-wrap gap-2">
        <span className="inline-flex items-center rounded-full bg-gray-800 px-3 py-1 text-xs text-gray-500 border border-gray-700 animate-pulse">
          Checking integrations…
        </span>
      </div>
    );
  }
  const ok = (v: boolean | undefined) => Boolean(v);
  const pill = (label: string, good: boolean) => (
    <span
      key={label}
      className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium border ${
        good
          ? 'bg-emerald-950/50 text-emerald-400 border-emerald-800/60'
          : 'bg-amber-950/40 text-amber-300 border-amber-800/50'
      }`}
    >
      {label}
      {good ? ' · OK' : ' · check env'}
    </span>
  );
  return (
    <div className="flex flex-wrap gap-2" aria-label="Integration status">
      {pill('Supabase', ok(health.supabase_configured))}
      {pill('Service role', ok(health.service_role_key_present))}
      {pill('LiveKit', ok(health.livekit_configured))}
    </div>
  );
}

function StatCardSkeleton() {
  return (
    <div className="card bg-gray-800/80 p-4 rounded-xl border border-gray-700 animate-pulse">
      <div className="h-3 w-24 rounded bg-gray-700 mb-3" />
      <div className="h-8 w-16 rounded bg-gray-700" />
    </div>
  );
}

function Dashboard() {
  const [stats, setStats] = useState<{ total_calls: number; total_bookings: number; avg_duration: number; booking_rate: number } | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);
  const [health, setHealth] = useState<HealthPayload | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const h = await fetch('/api/health');
        if (h.ok) setHealth(await h.json());
      } catch {
        setHealth({});
      }
    })();
  }, []);

  useEffect(() => {
    (async () => {
      setStatsLoading(true);
      try {
        const res = await authFetch('/api/stats');
        if (!res.ok) return;
        setStats(await res.json());
      } finally {
        setStatsLoading(false);
      }
    })();
  }, []);

  return (
    <div className="page p-8 max-w-7xl mx-auto">
      <div className="flex flex-col gap-4 sm:flex-row sm:justify-between sm:items-start mb-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight mb-2">Dashboard</h1>
          <p className="text-gray-400 text-sm max-w-xl">Call performance and live voice tests. Metrics use your workspace data from Supabase.</p>
        </div>
        <IntegrationPills health={health} />
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {statsLoading ? (
          <>
            <StatCardSkeleton />
            <StatCardSkeleton />
            <StatCardSkeleton />
            <StatCardSkeleton />
          </>
        ) : (
          <>
            <StatCard label="Total Calls" value={stats?.total_calls} />
            <StatCard label="Bookings" value={stats?.total_bookings} />
            <StatCard label="Avg Duration (s)" value={stats?.avg_duration} />
            <StatCard label="Booking Rate (%)" value={stats?.booking_rate} />
          </>
        )}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <VoiceTester />
        <div className="card bg-gray-800/80 p-8 rounded-2xl border border-gray-700 min-h-64 flex flex-col items-center justify-center text-center ring-1 ring-white/5">
          {statsLoading ? (
            <div className="w-full space-y-3 animate-pulse">
              <div className="h-4 w-3/4 max-w-xs mx-auto rounded bg-gray-700" />
              <div className="h-24 w-full max-w-sm mx-auto rounded-xl bg-gray-700/50" />
            </div>
          ) : (stats?.total_calls ?? 0) === 0 ? (
            <>
              <p className="text-gray-300 font-medium mb-1">No call volume yet</p>
              <p className="text-gray-500 text-sm max-w-sm">Run a demo or outbound call. Trends and charts can plug in here once you have history.</p>
            </>
          ) : (
            <p className="text-gray-500 text-sm">Analytics charts can be added here (e.g. daily calls, booking funnel).</p>
          )}
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number | undefined }) {
  return (
    <div className="card bg-gray-800/80 p-4 rounded-xl border border-gray-700 ring-1 ring-white/5">
      <p className="text-gray-400 text-sm">{label}</p>
      <p className="text-2xl font-bold tabular-nums">{value ?? '—'}</p>
    </div>
  );
}

function CallLogs() {
  const [rows, setRows] = useState<any[]>([]);
  useEffect(() => {
    (async () => {
      const res = await authFetch('/api/logs');
      if (!res.ok) return;
      const data = await res.json();
      setRows(Array.isArray(data) ? data : []);
    })();
  }, []);

  return (
    <div className="page p-8">
      <h1 className="text-2xl font-bold mb-4">Call Logs</h1>
      <div className="space-y-3">
        {rows.slice(0, 30).map((r, i) => (
          <div key={i} className="bg-gray-800 border border-gray-700 rounded-xl p-4">
            <div className="text-xs text-gray-400">{r.created_at || '-'}</div>
            <div className="font-semibold">{r.phone || 'unknown'}</div>
            <div className="text-sm text-gray-300">{r.summary || 'No summary'}</div>
          </div>
        ))}
        {!rows.length && <p className="text-gray-400">No call logs yet.</p>}
      </div>
    </div>
  );
}

function Crm() {
  const [rows, setRows] = useState<any[]>([]);
  useEffect(() => {
    (async () => {
      const res = await authFetch('/api/contacts');
      if (!res.ok) return;
      const data = await res.json();
      setRows(Array.isArray(data) ? data : []);
    })();
  }, []);

  return (
    <div className="page p-8">
      <h1 className="text-2xl font-bold mb-4">CRM Contacts</h1>
      <div className="space-y-3">
        {rows.slice(0, 50).map((r, i) => (
          <div key={i} className="bg-gray-800 border border-gray-700 rounded-xl p-4">
            <div className="font-semibold">{r.caller_name || 'Unknown'}</div>
            <div className="text-sm text-gray-300">{r.phone || 'unknown'}</div>
            <div className="text-xs text-gray-400">Calls: {r.total_calls || 0}</div>
          </div>
        ))}
        {!rows.length && <p className="text-gray-400">No contacts yet.</p>}
      </div>
    </div>
  );
}

function Settings() {
  const [config, setConfig] = useState<any>({});
  const [message, setMessage] = useState('');

  useEffect(() => {
    (async () => {
      const res = await authFetch('/api/config');
      if (!res.ok) return;
      setConfig(await res.json());
    })();
  }, []);

  const onSave = async () => {
    setMessage('');
    const res = await authFetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    });
    const data = await res.json();
    setMessage(res.ok ? 'Config saved.' : data?.detail || 'Failed to save config.');
  };

  return (
    <div className="page p-8">
      <h1 className="text-2xl font-bold mb-4">Agent Settings</h1>
      <div className="max-w-2xl bg-gray-800 border border-gray-700 rounded-xl p-6 space-y-4">
        <label className="block">
          <span className="text-sm text-gray-400">First Line</span>
          <input
            className="mt-1 w-full rounded-lg bg-gray-900 border border-gray-700 px-3 py-2"
            value={config.first_line || ''}
            onChange={(e) => setConfig({ ...config, first_line: e.target.value })}
          />
        </label>
        <label className="block">
          <span className="text-sm text-gray-400">LLM Model</span>
          <input
            className="mt-1 w-full rounded-lg bg-gray-900 border border-gray-700 px-3 py-2"
            value={config.llm_model || ''}
            onChange={(e) => setConfig({ ...config, llm_model: e.target.value })}
          />
        </label>
        <button onClick={onSave} className="bg-indigo-600 hover:bg-indigo-500 px-4 py-2 rounded-lg">
          Save Settings
        </button>
        {message && <p className="text-sm text-gray-300">{message}</p>}
      </div>
    </div>
  );
}

function SidebarLink({ to, icon: Icon, children }: { to: string, icon: any, children: React.ReactNode }) {
  const location = useLocation();
  const isActive = location.pathname === to;
  return (
    <Link 
      to={to} 
      className={`nav-item flex items-center gap-3 px-6 py-3 transition-colors ${isActive ? 'bg-indigo-600/10 text-indigo-400 border-r-2 border-indigo-400' : 'hover:bg-gray-700 hover:text-white text-gray-400'}`}
    >
      <Icon size={20} weight={isActive ? "fill" : "regular"} /> {children}
    </Link>
  );
}

function Layout({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  return (
    <div className="layout flex h-screen bg-gray-900 text-gray-100">
      <nav className="sidebar w-64 bg-[#161b22] border-r border-gray-800 flex flex-col shrink-0">
        <div className="p-6 border-b border-gray-800">
          <h2 className="text-xl font-bold bg-gradient-to-r from-indigo-400 to-cyan-400 bg-clip-text text-transparent">RapidX Voice OS</h2>
          <p className="text-xs text-gray-500 mt-1 font-mono">build: antigravity-dev</p>
        </div>
        <div className="flex-1 py-4 flex flex-col gap-1">
          <SidebarLink to="/" icon={ChartLineUp}>Dashboard</SidebarLink>
          <SidebarLink to="/terminal" icon={TerminalWindow}>Terminal Logs</SidebarLink>
          <SidebarLink to="/logs" icon={PhoneCall}>Call History</SidebarLink>
          <SidebarLink to="/crm" icon={Users}>CRM Contacts</SidebarLink>
          <SidebarLink to="/settings" icon={Gear}>Settings</SidebarLink>
        </div>
        <div className="p-4 border-t border-gray-800 text-xs text-gray-500 text-center font-mono">
          <button
            onClick={() => {
              clearAccessToken();
              navigate('/login');
            }}
            className="mb-2 text-gray-300 hover:text-white"
          >
            Logout
          </button>
          <div>Powered by LiveKit & FastAPI</div>
        </div>
      </nav>
      <main className="flex-1 overflow-y-auto">
        {children}
      </main>
    </div>
  );
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  if (!getAccessToken()) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="*"
          element={
            <ProtectedRoute>
              <Layout>
                <Routes>
                  <Route path="/" element={<Dashboard />} />
                  <Route path="/terminal" element={<TerminalPage />} />
                  <Route path="/logs" element={<CallLogs />} />
                  <Route path="/crm" element={<Crm />} />
                  <Route path="/settings" element={<Settings />} />
                </Routes>
              </Layout>
            </ProtectedRoute>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
