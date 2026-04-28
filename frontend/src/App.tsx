import { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Link, useLocation, Navigate, useNavigate } from 'react-router-dom';
import { ArrowRight, ChartLineUp, CheckCircle, Gear, MicrophoneStage, PhoneCall, PlayCircle, ShieldCheck, Sparkle, TerminalWindow, Users, Waveform } from '@phosphor-icons/react';
import VoiceTester from './VoiceTester';
import TerminalPage from './Terminal';
import Login from './Login';
import { clearAccessToken, getAccessToken } from './auth';
import { api } from './lib/api';
import heroAsset from './assets/hero.png';
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

function useScrollReveal() {
  useEffect(() => {
    const elements = Array.from(document.querySelectorAll<HTMLElement>('[data-reveal]'));
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible');
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.18, rootMargin: '0px 0px -64px 0px' },
    );
    elements.forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, []);
}

function JettoneLogo() {
  return (
    <span className="jettone-logo" aria-hidden="true">
      <Waveform size={22} weight="bold" />
    </span>
  );
}

function LandingPage() {
  useScrollReveal();

  const metrics = [
    ['91%', 'faster first response'],
    ['24/7', 'consumer call coverage'],
    ['4.8/5', 'average caller rating'],
  ];
  const features = [
    { title: 'Answer every shopper', copy: 'Jettone handles product questions, booking requests, delivery updates, and missed calls with a polished consumer voice.', Icon: PhoneCall },
    { title: 'Resolve before handoff', copy: 'Collect the reason, verify intent, summarize the issue, and route only the calls that need your team.', Icon: CheckCircle },
    { title: 'Protect the brand', copy: 'Guardrails, transcripts, sentiment, and escalation logic keep every customer interaction on-message.', Icon: ShieldCheck },
  ];
  const useCases = ['Appointments', 'Order status', 'Subscriptions', 'Local services', 'Healthcare intake', 'Home services'];
  const integrations = ['Shopify', 'Stripe', 'Calendly', 'HubSpot', 'Zendesk', 'WhatsApp'];

  return (
    <main className="min-h-screen bg-[#05070b] text-slate-100">
      <section className="landing-hero relative min-h-[92svh] overflow-hidden border-b border-white/10">
        <img src={heroAsset} alt="" className="landing-hero-asset" />
        <div className="landing-grid" />
        <nav className="relative z-10 mx-auto flex w-full max-w-7xl items-center justify-between px-6 py-5">
          <Link to="/" className="flex items-center gap-3" aria-label="Jettone home">
            <JettoneLogo />
            <span>
              <span className="block text-lg font-black leading-none">Jettone</span>
              <span className="block text-xs text-cyan-100/70">Consumer voice agents</span>
            </span>
          </Link>
          <div className="hidden items-center gap-8 text-sm text-slate-300 md:flex">
            <a href="#platform" className="hover:text-white">Platform</a>
            <a href="#consumer" className="hover:text-white">B2C workflows</a>
            <a href="#integrations" className="hover:text-white">Stack</a>
          </div>
          <div className="flex items-center gap-3">
            <Link to="/login" className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-200 hover:bg-white/10">Login</Link>
            <Link to="/login" className="hidden rounded-lg bg-cyan-300 px-4 py-2 text-sm font-bold text-slate-950 shadow-lg shadow-cyan-950/30 hover:bg-cyan-200 sm:inline-flex">
              Launch agent
            </Link>
          </div>
        </nav>

        <div className="relative z-10 mx-auto grid min-h-[calc(92svh-82px)] w-full max-w-7xl items-center gap-10 px-6 pb-12 pt-4 lg:grid-cols-[1fr_0.95fr]">
          <div className="max-w-3xl" data-reveal>
            <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-cyan-300/25 bg-cyan-300/10 px-3 py-1 text-sm text-cyan-100">
              <Sparkle size={16} weight="fill" />
              Billion-dollar voice layer for consumer brands
            </div>
            <h1 className="max-w-4xl text-5xl font-black leading-[1.02] tracking-normal text-white md:text-7xl">
              Jettone turns every consumer call into a premium customer moment.
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-300">
              AI calling agents for clinics, salons, local services, ecommerce, and subscription businesses that need fast, human-grade conversations at consumer scale.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link to="/login" className="inline-flex items-center justify-center gap-2 rounded-lg bg-cyan-300 px-5 py-3 font-bold text-slate-950 shadow-xl shadow-cyan-950/30 hover:bg-cyan-200">
                Build Jettone <ArrowRight size={18} weight="bold" />
              </Link>
              <Link to="/login" className="inline-flex items-center justify-center gap-2 rounded-lg border border-white/15 bg-white/5 px-5 py-3 font-semibold text-white hover:bg-white/10">
                <PlayCircle size={20} weight="fill" /> Hear the agent
              </Link>
            </div>
            <div className="mt-10 grid max-w-2xl grid-cols-3 gap-3">
              {metrics.map(([value, label]) => (
                <div key={label} className="border-l border-cyan-300/40 pl-4">
                  <div className="text-2xl font-black text-white">{value}</div>
                  <div className="mt-1 text-sm text-slate-400">{label}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="landing-console relative mx-auto w-full max-w-lg rounded-xl border border-white/12 bg-slate-950/72 p-4 shadow-2xl shadow-black/40 backdrop-blur" data-reveal>
            <div className="mb-4 flex items-center justify-between border-b border-white/10 pb-3">
              <div>
                <p className="text-xs uppercase text-cyan-200/70">Live consumer call</p>
                <p className="font-semibold text-white">Jettone Concierge</p>
              </div>
              <span className="inline-flex items-center gap-2 rounded-full bg-cyan-300/10 px-3 py-1 text-xs font-semibold text-cyan-200">
                <span className="h-2 w-2 rounded-full bg-cyan-300" /> Live
              </span>
            </div>
            <div className="space-y-3">
              <div className="max-w-[82%] rounded-lg bg-white/8 p-3 text-sm text-slate-200">
                I missed a call. Can I still book a skin consultation for tomorrow?
              </div>
              <div className="ml-auto max-w-[86%] rounded-lg bg-cyan-300 p-3 text-sm font-medium text-slate-950">
                Absolutely. I found two openings, confirmed your preferences, and can reserve the 4:30 slot now.
              </div>
              <div className="rounded-lg border border-white/10 bg-black/25 p-3">
                <div className="mb-3 flex items-center justify-between text-xs text-slate-400">
                  <span>Consumer intelligence</span>
                  <MicrophoneStage size={18} className="text-cyan-200" />
                </div>
                <div className="grid grid-cols-3 gap-2 text-center text-xs">
                  <div className="rounded-md bg-white/7 p-2">
                    <p className="text-slate-400">Mood</p>
                    <p className="mt-1 font-bold text-white">Ready</p>
                  </div>
                  <div className="rounded-md bg-white/7 p-2">
                    <p className="text-slate-400">Need</p>
                    <p className="mt-1 font-bold text-white">Book</p>
                  </div>
                  <div className="rounded-md bg-white/7 p-2">
                    <p className="text-slate-400">Action</p>
                    <p className="mt-1 font-bold text-white">Confirm</p>
                  </div>
                </div>
              </div>
              <div className="flex h-12 items-end gap-1 rounded-lg bg-black/25 px-3 py-2" aria-hidden="true">
                {[18, 28, 14, 38, 24, 42, 16, 34, 26, 44, 18, 30, 20, 36, 22, 40].map((height, index) => (
                  <span key={index} className="voice-bar w-full rounded-t bg-cyan-300/80" style={{ height, animationDelay: `${index * 70}ms` }} />
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="platform" className="bg-[#f7f8fb] px-6 py-20 text-slate-950">
        <div className="mx-auto max-w-7xl" data-reveal>
          <div className="mb-10 max-w-2xl">
            <p className="mb-3 text-sm font-bold uppercase text-cyan-700">Platform</p>
            <h2 className="text-3xl font-black tracking-normal md:text-5xl">A voice agent built for people buying, booking, asking, and deciding.</h2>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            {features.map(({ title, copy, Icon }) => (
              <article key={title} className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
                <Icon size={28} weight="duotone" className="mb-5 text-cyan-700" />
                <h3 className="text-xl font-bold">{title}</h3>
                <p className="mt-3 leading-7 text-slate-600">{copy}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section id="consumer" className="bg-white px-6 py-20 text-slate-950">
        <div className="mx-auto grid max-w-7xl gap-8 lg:grid-cols-[0.9fr_1.1fr]" data-reveal>
          <div>
            <p className="mb-3 text-sm font-bold uppercase text-cyan-700">B2C only</p>
            <h2 className="text-3xl font-black tracking-normal md:text-5xl">No enterprise clutter. Just calls that make consumers feel handled.</h2>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {useCases.map((item) => (
              <div key={item} className="flex items-center gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4 font-semibold">
                <CheckCircle size={21} weight="fill" className="text-cyan-600" />
                {item}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="integrations" className="bg-[#05070b] px-6 py-20 text-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-8 md:flex-row md:items-center md:justify-between" data-reveal>
          <div className="max-w-xl">
            <p className="mb-3 text-sm font-bold uppercase text-cyan-200">Connected stack</p>
            <h2 className="text-3xl font-black tracking-normal md:text-5xl">Jettone fits beside the tools consumer teams already run.</h2>
          </div>
          <div className="grid w-full max-w-xl grid-cols-2 gap-3 sm:grid-cols-3">
            {integrations.map((item) => (
              <div key={item} className="rounded-lg border border-white/12 bg-white/7 px-4 py-4 text-center font-semibold text-slate-100">
                {item}
              </div>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}

function Dashboard() {
  const [stats, setStats] = useState<{ total_calls: number; total_bookings: number; avg_duration: number; booking_rate: number } | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);
  const [health, setHealth] = useState<HealthPayload | null>(null);

  useEffect(() => {
    (async () => {
      try {
        setHealth(await api.health());
      } catch {
        setHealth({});
      }
    })();
  }, []);

  useEffect(() => {
    (async () => {
      setStatsLoading(true);
      try {
        setStats(await api.analytics());
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
      setRows(await api.calls());
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
      setRows(await api.contacts());
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
      setConfig(await api.config());
    })();
  }, []);

  const onSave = async () => {
    setMessage('');
    try {
      await api.saveConfig(config);
      setMessage('Config saved.');
    } catch (error: any) {
      setMessage(error?.message || 'Failed to save config.');
    }
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

function ResourceList({ title, loader, emptyText }: { title: string; loader: () => Promise<any[]>; emptyText: string }) {
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        setRows(await loader());
      } finally {
        setLoading(false);
      }
    })();
  }, [loader]);

  return (
    <div className="page p-8">
      <h1 className="text-2xl font-bold mb-4">{title}</h1>
      {loading ? (
        <p className="text-gray-400">Loading...</p>
      ) : rows.length ? (
        <div className="space-y-3">
          {rows.slice(0, 50).map((row, index) => (
            <pre key={row.id || index} className="overflow-auto rounded-xl border border-gray-700 bg-gray-800 p-4 text-xs text-gray-200">
              {JSON.stringify(row, null, 2)}
            </pre>
          ))}
        </div>
      ) : (
        <p className="text-gray-400">{emptyText}</p>
      )}
    </div>
  );
}

function Agents() {
  return <ResourceList title="Agents" loader={api.agents} emptyText="No agents returned by /api/agents yet." />;
}

function Campaigns() {
  return <ResourceList title="Campaigns" loader={api.campaigns} emptyText="No campaigns returned by /api/campaigns yet." />;
}

function Analytics() {
  const [stats, setStats] = useState<{ total_calls: number; total_bookings: number; avg_duration: number; booking_rate: number } | null>(null);

  useEffect(() => {
    (async () => {
      setStats(await api.analytics());
    })();
  }, []);

  return (
    <div className="page p-8">
      <h1 className="text-2xl font-bold mb-4">Analytics</h1>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total Calls" value={stats?.total_calls} />
        <StatCard label="Bookings" value={stats?.total_bookings} />
        <StatCard label="Avg Duration (s)" value={stats?.avg_duration} />
        <StatCard label="Booking Rate (%)" value={stats?.booking_rate} />
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
          <SidebarLink to="/dashboard" icon={ChartLineUp}>Dashboard</SidebarLink>
          <SidebarLink to="/agents" icon={Users}>Agents</SidebarLink>
          <SidebarLink to="/terminal" icon={TerminalWindow}>Terminal Logs</SidebarLink>
          <SidebarLink to="/logs" icon={PhoneCall}>Calls</SidebarLink>
          <SidebarLink to="/campaigns" icon={PlayCircle}>Campaigns</SidebarLink>
          <SidebarLink to="/analytics" icon={ChartLineUp}>Analytics</SidebarLink>
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
  const [loading, setLoading] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);

  useEffect(() => {
    (async () => {
      setAuthenticated(Boolean(await getAccessToken()));
      setLoading(false);
    })();
  }, []);

  if (loading) {
    return <div className="min-h-screen bg-gray-900 text-gray-300 p-8">Loading...</div>;
  }

  if (!authenticated) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<Login />} />
        <Route
          path="*"
          element={
            <ProtectedRoute>
              <Layout>
                <Routes>
                  <Route path="/dashboard" element={<Dashboard />} />
                  <Route path="/agents" element={<Agents />} />
                  <Route path="/terminal" element={<TerminalPage />} />
                  <Route path="/logs" element={<CallLogs />} />
                  <Route path="/campaigns" element={<Campaigns />} />
                  <Route path="/analytics" element={<Analytics />} />
                  <Route path="/crm" element={<Crm />} />
                  <Route path="/settings" element={<Settings />} />
                  <Route path="*" element={<Navigate to="/dashboard" replace />} />
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
