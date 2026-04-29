import { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Link, useLocation, Navigate, useNavigate } from 'react-router-dom';
import {
  ArrowRight,
  ArrowSquareOut,
  BookOpen,
  CaretUpDown,
  ChartLineUp,
  ChatCircleText,
  CheckCircle,
  Code,
  Copy,
  CreditCard,
  Database,
  DownloadSimple,
  FileText,
  Flask,
  FloppyDisk,
  Gear,
  GitBranch,
  Hash,
  Info,
  ListBullets,
  MagnifyingGlass,
  MicrophoneStage,
  PhoneCall,
  PhoneIncoming,
  PlayCircle,
  Plus,
  PlugsConnected,
  ShareNetwork,
  ShieldCheck,
  Sparkle,
  Stack,
  TerminalWindow,
  Trash,
  Translate,
  Users,
  Waveform,
  Wrench,
} from '@phosphor-icons/react';
import VoiceTester from './VoiceTester';
import TerminalPage from './Terminal';
import Login from './Login';
import { clearAccessToken, getAccessToken } from './auth';
import { api, apiConnectionMessage, isApiConfigured, type AnalyticsSummary, type BillingSummary, type Campaign, type CurrentUser, type WorkspaceSummary } from './lib/api';
import { supabase } from './lib/supabase';
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

function useScrollReveal() {
  useEffect(() => {
    const elements = Array.from(document.querySelectorAll<HTMLElement>('[data-reveal]'));
    if (typeof IntersectionObserver === 'undefined') {
      elements.forEach((element) => element.classList.add('is-visible'));
      return;
    }
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

type DemoAgent = {
  id: string;
  name: string;
  status: string;
  phone: string;
  welcomeMessage: string;
  prompt: string;
};

const demoAgents: DemoAgent[] = [
  {
    id: 'maxrindia',
    name: 'maxrindia',
    status: 'Active',
    phone: '+918065480786',
    welcomeMessage: 'வணக்கம்! keystone Real Estate-க்கு அழைத்ததற்கு நன்றி, நான் sajitha பேசுகிறேன், நீங்கள் எப்படிச் உதவி வேண்டும்?',
    prompt:
      'நீங்கள் shajitha, Keystone real Estate-ல் இருந்து பேசும் ஒரு நட்பான மற்றும் professional inbound real estate assistant.\n\nWelcome\nநன்றி Keystone Estateக்கு call பண்ணதுக்கு. நீங்கள் Chennaiல property வாங்க அல்லது rent செய்ய பார்க்கிறீங்களா?\n\nGoals\n- Caller name, phone, location preference, budget, property type collect செய்யவும்.\n- Site visit அல்லது callback book செய்யவும்.\n- If caller asks for human, transfer politely.\n\nStyle\nTamil primary, clear short sentences, warm tone, no long monologues.',
  },
  {
    id: 'real-estate-sales-agent',
    name: 'real estate sales agent',
    status: 'Active',
    phone: '+919876543210',
    welcomeMessage: 'Hi, thanks for calling Keystone Real Estate. I can help you with property details, pricing, and site visits.',
    prompt:
      'You are a professional real estate sales assistant. Qualify buyer intent, collect location and budget, answer common questions, and book a site visit.',
  },
  {
    id: 'my-new-agent',
    name: 'My New Agent',
    status: 'Draft',
    phone: '+910000000000',
    welcomeMessage: 'Hello, thanks for calling. How can I help you today?',
    prompt: 'You are a helpful voice agent. Keep replies short, natural, and useful.',
  },
];

const agentTabs = [
  ['Agent', FileText],
  ['LLM', Gear],
  ['Audio', Translate],
  ['Engine', Wrench],
  ['Call', PhoneCall],
  ['Tools', Code],
  ['Analytics', ChartLineUp],
  ['Inbound', PhoneIncoming],
] as const;

function ShellButton({ children, primary = false, danger = false, className = '', onClick }: { children: React.ReactNode; primary?: boolean; danger?: boolean; className?: string; onClick?: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex min-h-10 items-center justify-center gap-2 rounded-md border px-4 text-sm font-semibold shadow-sm transition ${
        primary
          ? 'border-blue-600 bg-blue-600 text-white hover:bg-blue-700'
          : danger
            ? 'border-slate-200 bg-white text-slate-900 hover:border-red-200 hover:bg-red-50 hover:text-red-700'
            : 'border-slate-200 bg-white text-slate-950 hover:bg-slate-50'
      } ${className}`}
    >
      {children}
    </button>
  );
}

function AppPanel({ title, icon: Icon, children, action }: { title: string; icon?: any; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between gap-4">
        <h2 className="flex items-center gap-2 text-lg font-bold text-slate-950">
          {Icon && <Icon size={19} className="text-slate-400" />}
          {title}
          <Info size={16} className="text-slate-400" />
        </h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function Agents() {
  const [agents, setAgents] = useState<DemoAgent[]>(demoAgents);
  const [selectedId, setSelectedId] = useState(demoAgents[0].id);
  const [search, setSearch] = useState('');
  const [activeTab, setActiveTab] = useState('Agent');
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    (async () => {
      const rows = await api.agents();
      if (!rows.length) return;
      setAgents((current) => {
        const mapped = rows.map((row: any, index: number) => ({
          id: row.id || `agent-${index}`,
          name: row.name || row.config?.name || `Agent ${index + 1}`,
          status: row.status || 'Active',
          phone: row.phone || row.config?.phone || '+918065480786',
          welcomeMessage: row.config?.welcomeMessage || row.config?.first_line || demoAgents[0].welcomeMessage,
          prompt: row.config?.prompt || row.config?.agent_instructions || demoAgents[0].prompt,
        }));
        setSelectedId(mapped[0]?.id || current[0].id);
        return mapped;
      });
    })();
  }, []);

  const selected = agents.find((agent) => agent.id === selectedId) || agents[0];
  const filtered = agents.filter((agent) => agent.name.toLowerCase().includes(search.toLowerCase()));
  const updateSelected = (fields: Partial<DemoAgent>) => {
    setSaved(false);
    setAgents((current) => current.map((agent) => (agent.id === selected.id ? { ...agent, ...fields } : agent)));
  };

  return (
    <div className="min-h-full bg-slate-50 px-6 py-4 text-slate-950">
      <p className="mb-5 text-sm text-slate-600">Fine tune your agents</p>
      <div className="grid h-[calc(100vh-56px)] min-h-[720px] grid-cols-[376px_minmax(620px,1fr)_304px] overflow-hidden rounded-lg border border-slate-200 bg-white shadow-xl shadow-slate-200/70">
        <aside className="border-r border-slate-200 bg-white">
          <div className="border-b border-slate-200 p-5">
            <h1 className="mb-3 text-2xl font-black text-slate-950">Your Agents</h1>
            <div className="flex gap-3">
              <ShellButton><DownloadSimple size={18} /> Import</ShellButton>
              <ShellButton><Plus size={18} /> New Agent</ShellButton>
            </div>
          </div>
          <div className="space-y-3 p-5">
            <label className="flex items-center gap-3 rounded-md border border-slate-200 bg-white px-4 py-3 text-slate-500 shadow-sm">
              <MagnifyingGlass size={21} />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                className="w-full bg-transparent text-base text-slate-900 outline-none placeholder:text-slate-400"
                placeholder="Search agents..."
              />
            </label>
            {filtered.map((agent) => (
              <button
                key={agent.id}
                type="button"
                onClick={() => setSelectedId(agent.id)}
                className={`w-full rounded-lg border px-4 py-4 text-left text-base font-semibold transition ${
                  selected.id === agent.id ? 'border-slate-300 bg-slate-100' : 'border-slate-200 bg-white hover:bg-slate-50'
                }`}
              >
                {agent.name}
              </button>
            ))}
          </div>
        </aside>

        <main className="overflow-y-auto bg-white p-5">
          <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
            <div className="grid grid-cols-[minmax(280px,1fr)_auto_auto] items-center gap-7">
              <input
                value={selected.name}
                onChange={(event) => updateSelected({ name: event.target.value })}
                className="h-12 rounded-md border border-transparent bg-white text-4xl font-normal text-slate-950 outline-none shadow-sm focus:border-slate-200"
              />
              <ShellButton><Copy size={20} /> Agent ID</ShellButton>
              <ShellButton><ShareNetwork size={20} /> Share</ShellButton>
            </div>
            <div className="mt-5 grid grid-cols-[minmax(340px,520px)_1fr] items-start gap-6">
              <div>
                <p className="mb-2 flex items-center gap-2 text-sm text-slate-900"><Info size={16} /> Cost per min: ~ $0.067</p>
                <div className="flex h-3 overflow-hidden rounded-full bg-slate-200">
                  <span className="w-[18%] bg-teal-500" />
                  <span className="w-[22%] bg-orange-500" />
                  <span className="w-[47%] bg-slate-700" />
                  <span className="w-[13%] bg-blue-600" />
                </div>
                <div className="mt-3 flex flex-wrap gap-4 text-sm text-slate-600">
                  {['Transcriber', 'LLM', 'Voice', 'Telephony', 'Platform'].map((item, index) => (
                    <span key={item} className="flex items-center gap-2">
                      <span className={`h-2.5 w-2.5 rounded-full ${['bg-teal-500', 'bg-orange-500', 'bg-slate-700', 'bg-amber-400', 'bg-blue-600'][index]}`} />
                      {item}
                    </span>
                  ))}
                </div>
              </div>
              <p className="flex items-center gap-2 text-sm text-slate-500"><Info size={16} /> India routing</p>
            </div>
          </section>

          <div className="my-5 grid grid-cols-8 rounded-lg bg-slate-100 p-1">
            {agentTabs.map(([label, Icon]) => (
              <button
                key={label}
                type="button"
                onClick={() => setActiveTab(label)}
                className={`flex min-h-14 flex-col items-center justify-center gap-1 rounded-md text-sm font-semibold transition ${
                  activeTab === label ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-700 hover:bg-white/60'
                }`}
              >
                <Icon size={20} />
                {label}
              </button>
            ))}
          </div>

          {activeTab === 'Agent' ? (
            <div className="space-y-5">
              <AppPanel title="Agent Welcome Message" icon={ChatCircleText}>
                <input
                  value={selected.welcomeMessage}
                  onChange={(event) => updateSelected({ welcomeMessage: event.target.value })}
                  className="w-full rounded-md border border-slate-200 px-4 py-3 text-lg text-slate-950 shadow-inner outline-none focus:border-blue-400"
                />
                <p className="mt-2 text-sm text-slate-500">You can define variables using {'{variable_name}'}</p>
              </AppPanel>
              <AppPanel
                title="Agent Prompt"
                icon={FileText}
                action={<ShellButton><Gear size={17} /> AI Edit</ShellButton>}
              >
                <div className="mb-5 flex flex-wrap gap-2">
                  <button type="button" className="rounded-md bg-blue-600 px-4 py-2 text-sm font-bold text-white">Tamil (Primary)</button>
                  <ShellButton><Plus size={17} /> Add Language</ShellButton>
                </div>
                <textarea
                  value={selected.prompt}
                  onChange={(event) => updateSelected({ prompt: event.target.value })}
                  className="h-72 w-full resize-none rounded-md border border-slate-200 bg-white p-4 text-lg leading-7 text-slate-950 outline-none focus:border-blue-400"
                />
              </AppPanel>
            </div>
          ) : (
            <AppPanel title={`${activeTab} Settings`} icon={SlidersIcon}>
              <div className="grid gap-4 md:grid-cols-2">
                <SettingField label={`${activeTab} model`} value="Production default" />
                <SettingField label="Fallback behavior" value="Escalate to human" />
                <SettingField label="Response style" value="Short, warm, professional" />
                <SettingField label="Status" value="Enabled" />
              </div>
            </AppPanel>
          )}
        </main>

        <aside className="space-y-5 border-l border-slate-200 bg-white p-4">
          <div className="rounded-lg border border-slate-200 p-4">
            <ShellButton primary className="mb-4 w-full"><PhoneIncoming size={20} /> Get call from agent</ShellButton>
            <div className="mb-2 flex items-center justify-between gap-2">
              <div className="flex min-h-11 flex-1 items-center gap-2 rounded-md bg-slate-100 px-3 font-bold">
                <PhoneCall size={20} />
                {selected.phone}
              </div>
              <ShellButton className="px-3"><Gear size={19} /></ShellButton>
            </div>
            <button type="button" className="w-full text-right text-sm text-blue-600">Purchase phone numbers <ArrowSquareOut size={12} className="inline" /></button>
          </div>

          <div className="rounded-lg border border-slate-200 p-4">
            <ShellButton className="mb-5 w-full text-base">See all call logs <ArrowSquareOut size={20} /></ShellButton>
            <div className="grid grid-cols-[1fr_auto] gap-2">
              <ShellButton primary onClick={() => { setSaved(true); }}><FloppyDisk size={20} /> {saved ? 'Saved' : 'Save agent'}</ShellButton>
              <ShellButton danger className="px-3"><Trash size={20} /></ShellButton>
            </div>
            <p className="mt-3 border-b border-slate-200 pb-5 text-sm italic text-slate-500">Updated 8 days ago</p>
            <ShellButton className="mt-6 w-full bg-slate-100 text-blue-600"><ChatCircleText size={20} /> Chat with agent</ShellButton>
            <p className="mt-3 text-center text-sm text-slate-500">Chat is the fastest way to test and refine.</p>
            <div className="mt-6 rounded-lg border border-dashed border-slate-300 p-4 text-center">
              <ShellButton className="w-full border-dashed"><Flask size={20} /> Test via browser <span className="rounded bg-slate-100 px-2 py-1 text-xs text-slate-500">BETA</span></ShellButton>
              <p className="mt-3 text-xs text-slate-500">For best experience, use "Get call from agent"</p>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

function SlidersIcon({ size = 20, className = '' }: { size?: number; className?: string }) {
  return <Gear size={size} className={className} />;
}

function SettingField({ label, value }: { label: string; value: string }) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-slate-600">{label}</span>
      <input className="mt-2 w-full rounded-md border border-slate-200 px-3 py-2 text-slate-900 outline-none focus:border-blue-400" defaultValue={value} />
    </label>
  );
}

function Dashboard() {
  const [stats, setStats] = useState<AnalyticsSummary | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);
  const [health, setHealth] = useState<HealthPayload | null>(null);

  useEffect(() => {
    (async () => {
      try {
        setHealth(await api.health());
        setStats(await api.analytics());
      } finally {
        setStatsLoading(false);
      }
    })();
  }, []);

  return (
    <AppPage title="Dashboard" subtitle="Call performance and launch readiness for your voice agents.">
      <IntegrationPills health={health} />
      <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {statsLoading ? Array.from({ length: 4 }).map((_, index) => <StatCardSkeleton key={index} />) : (
          <>
            <StatCard label="Total Calls" value={stats?.total_calls} />
            <StatCard label="Answered" value={stats?.answered_calls} />
            <StatCard label="Failed" value={stats?.failed_calls} />
            <StatCard label="Total Minutes" value={stats?.total_minutes} />
            <StatCard label="Avg Duration (s)" value={stats?.avg_duration} />
            <StatCard label="AI Cost ($)" value={stats?.estimated_ai_cost} />
            <StatCard label="Bookings" value={stats?.total_bookings} />
            <StatCard label="Booking Rate (%)" value={stats?.booking_rate} />
          </>
        )}
      </div>
      <div className="mt-6 grid gap-5 xl:grid-cols-2">
        <CallNowCard />
        <OnboardingChecklist health={health} />
        <div className="rounded-lg border border-slate-200 bg-white p-6">
          <VoiceTester />
        </div>
      </div>
    </AppPage>
  );
}

function CallNowCard() {
  const [phoneNumber, setPhoneNumber] = useState('');
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const startCall = async () => {
    setStatus('');
    setError('');
    setLoading(true);
    try {
      const result = await api.callNow(phoneNumber);
      setStatus(`Dispatched ${result.phone_number} in ${result.room_name}`);
    } catch (err: any) {
      setError(err?.message || 'Call failed to dispatch.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-md bg-blue-50 text-blue-600">
        <PhoneCall size={26} weight="fill" />
      </div>
      <h2 className="text-xl font-bold text-slate-950">Call Now</h2>
      <p className="mt-2 text-sm text-slate-500">Trigger a real outbound LiveKit SIP call through the Railway backend.</p>
      <label className="mt-5 block">
        <span className="text-sm font-medium text-slate-600">Phone number</span>
        <input
          value={phoneNumber}
          onChange={(event) => setPhoneNumber(event.target.value)}
          placeholder="+919876543210"
          className="mt-2 w-full rounded-md border border-slate-200 px-4 py-3 text-slate-950 outline-none focus:border-blue-400"
        />
      </label>
      <ShellButton primary onClick={startCall} className="mt-5 w-full" >
        {loading ? 'Dispatching...' : 'Call Now'}
      </ShellButton>
      {status && <p className="mt-4 text-sm text-emerald-600">{status}</p>}
      {error && <p className="mt-4 text-sm text-red-600">{error}</p>}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number | undefined }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-2 text-3xl font-black tabular-nums text-slate-950">{value ?? '-'}</p>
    </div>
  );
}

function StatCardSkeleton() {
  return (
    <div className="animate-pulse rounded-lg border border-slate-200 bg-white p-4">
      <div className="h-3 w-24 rounded bg-slate-200" />
      <div className="mt-4 h-8 w-16 rounded bg-slate-200" />
    </div>
  );
}

function OnboardingChecklist({ health }: { health: HealthPayload | null }) {
  const items = [
    ['Create account', true],
    ['Connect Supabase', Boolean(health?.supabase_configured)],
    ['Add service role key', Boolean(health?.service_role_key_present)],
    ['Connect LiveKit', Boolean(health?.livekit_configured)],
  ] as const;

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold text-slate-950">Launch checklist</h2>
          <p className="text-sm text-slate-500">Everything needed before customers use calls.</p>
        </div>
        <ShieldCheck size={24} weight="duotone" className="text-blue-600" />
      </div>
      <div className="space-y-3">
        {items.map(([label, done]) => (
          <div key={label} className="flex items-center justify-between rounded-md bg-slate-50 px-3 py-2">
            <span className="text-sm text-slate-700">{label}</span>
            <span className={`text-xs font-semibold ${done ? 'text-emerald-600' : 'text-amber-600'}`}>
              {done ? 'Ready' : 'Needs setup'}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function CallLogs() {
  const [rows, setRows] = useState<any[]>([]);
  useEffect(() => {
    (async () => setRows(await api.calls()))();
  }, []);

  return (
    <AppPage title="Call History" subtitle="Review recent customer conversations and call summaries.">
      <DataList
        rows={rows.slice(0, 30)}
        emptyText="No call logs yet."
        render={(row, index) => (
          <div key={row.id || index} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <div className="text-xs text-slate-500">{row.created_at || '-'}</div>
            <div className="mt-1 font-semibold text-slate-950">{row.phone || 'unknown'}</div>
            <div className="mt-1 text-sm text-slate-600">{row.summary || 'No summary'}</div>
          </div>
        )}
      />
    </AppPage>
  );
}

function Crm() {
  const [rows, setRows] = useState<any[]>([]);
  useEffect(() => {
    (async () => setRows(await api.contacts()))();
  }, []);

  return (
    <AppPage title="CRM Contacts" subtitle="Contacts discovered from call activity.">
      <DataList
        rows={rows.slice(0, 50)}
        emptyText="No contacts yet."
        render={(row, index) => (
          <div key={row.phone || index} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <div className="font-semibold text-slate-950">{row.caller_name || 'Unknown'}</div>
            <div className="text-sm text-slate-600">{row.phone || 'unknown'}</div>
            <div className="text-xs text-slate-500">Calls: {row.total_calls || 0}</div>
          </div>
        )}
      />
    </AppPage>
  );
}

function Settings() {
  const [config, setConfig] = useState<any>({});
  const [message, setMessage] = useState('');

  useEffect(() => {
    (async () => setConfig(await api.config()))();
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
    <AppPage title="Agent Settings" subtitle="Tune default behavior and model configuration.">
      <div className="max-w-3xl rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <SettingField label="First Line" value={config.first_line || ''} />
        <div className="mt-4" />
        <SettingField label="LLM Model" value={config.llm_model || ''} />
        <ShellButton primary onClick={onSave} className="mt-5"><FloppyDisk size={18} /> Save Settings</ShellButton>
        {message && <p className="mt-3 text-sm text-slate-600">{message}</p>}
      </div>
    </AppPage>
  );
}

function ResourceList({ title, emptyText, icon: Icon }: { title: string; emptyText: string; icon: any }) {
  return (
    <AppPage title={title} subtitle="This module is ready for the next production workflow.">
      <div className="rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center shadow-sm">
        <Icon size={34} className="mx-auto mb-4 text-blue-600" />
        <p className="font-semibold text-slate-950">{emptyText}</p>
        <p className="mt-2 text-sm text-slate-500">The navigation and SaaS surface are in place; backend persistence can be added per module.</p>
      </div>
    </AppPage>
  );
}

function Campaigns() {
  const [rows, setRows] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        setRows(await api.campaigns());
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <AppPage title="Campaigns" subtitle="Outbound batches and their progress.">
      <div className="mb-5 flex justify-end"><ShellButton><Plus size={18} /> New campaign</ShellButton></div>
      {loading ? <p className="text-slate-500">Loading...</p> : rows.length ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {rows.map((row, index) => (
            <div key={row.id || index} className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
              <div className="mb-4 flex items-start justify-between gap-4">
                <div>
                  <h2 className="font-bold text-slate-950">{row.name || 'Untitled campaign'}</h2>
                  <p className="text-xs text-slate-500">{row.created_at || 'No date'}</p>
                </div>
                <span className="rounded-full border border-blue-100 bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">{row.status || 'draft'}</span>
              </div>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <StatCard label="Total calls" value={row.total_calls ?? 0} />
                <StatCard label="Completed" value={row.completed_calls ?? 0} />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center shadow-sm">
          <p className="font-semibold text-slate-950">No campaigns yet</p>
          <p className="mt-2 text-sm text-slate-500">Single calls are ready now. Campaign creation is the next production workflow.</p>
        </div>
      )}
    </AppPage>
  );
}

function Billing() {
  const [billing, setBilling] = useState<BillingSummary | null>(null);

  useEffect(() => {
    (async () => setBilling(await api.billing()))();
  }, []);

  return (
    <AppPage title="Billing" subtitle="Usage and trial billing summary.">
      <div className="grid gap-4 md:grid-cols-3">
        <StatCard label="Plan" value={undefined} />
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-sm text-slate-500">Current plan</p>
          <p className="mt-2 text-3xl font-black text-slate-950">{billing?.plan || 'Launch'}</p>
          <p className="mt-1 text-sm text-blue-600">{billing?.status || 'trial'}</p>
        </div>
        <StatCard label="Included minutes" value={billing?.included_minutes} />
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-sm text-slate-500">Next invoice estimate</p>
          <p className="mt-2 text-3xl font-black text-slate-950">${billing?.next_invoice_estimate ?? 0}</p>
          <p className="mt-1 text-sm text-slate-500">Used: {billing?.used_minutes ?? 0} min</p>
        </div>
      </div>
    </AppPage>
  );
}

function Admin() {
  const [me, setMe] = useState<CurrentUser | null>(null);
  const [workspace, setWorkspace] = useState<WorkspaceSummary | null>(null);

  useEffect(() => {
    (async () => {
      const [user, workspaceSummary] = await Promise.all([api.me(), api.workspace()]);
      setMe(user);
      setWorkspace(workspaceSummary);
    })();
  }, []);

  return (
    <AppPage title="Workplace" subtitle="Workspace, role, and deployment readiness.">
      <div className="grid gap-4 lg:grid-cols-2">
        <InfoCard title="Workspace" rows={[
          ['Name', workspace?.name || 'Personal'],
          ['Role', workspace?.role || me?.role || 'member'],
          ['Members', String(workspace?.member_count ?? 1)],
          ['Workspace ID', workspace?.id || 'created after first authenticated request'],
        ]} />
        <InfoCard title="Current user" rows={[
          ['Email', me?.email || 'Loading...'],
          ['User ID', me?.user_id || 'Loading...'],
          ['App role', me?.role || 'user'],
        ]} />
      </div>
    </AppPage>
  );
}

function Analytics() {
  const [stats, setStats] = useState<AnalyticsSummary | null>(null);

  useEffect(() => {
    (async () => setStats(await api.analytics()))();
  }, []);

  return (
    <AppPage title="Analytics" subtitle="Performance metrics for your voice operation.">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Total Calls" value={stats?.total_calls} />
        <StatCard label="Answered Calls" value={stats?.answered_calls} />
        <StatCard label="Failed Calls" value={stats?.failed_calls} />
        <StatCard label="Avg Duration (s)" value={stats?.avg_duration} />
        <StatCard label="Total Minutes" value={stats?.total_minutes} />
        <StatCard label="Estimated AI Cost ($)" value={stats?.estimated_ai_cost} />
        <StatCard label="Bookings" value={stats?.total_bookings} />
      </div>
    </AppPage>
  );
}

function InfoCard({ title, rows }: { title: string; rows: string[][] }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="mb-4 text-lg font-bold text-slate-950">{title}</h2>
      <div className="space-y-3 text-sm">
        {rows.map(([label, value]) => (
          <p key={label} className="break-words text-slate-700"><span className="font-medium text-slate-500">{label}:</span> {value}</p>
        ))}
      </div>
    </div>
  );
}

function DataList({ rows, render, emptyText }: { rows: any[]; render: (row: any, index: number) => React.ReactNode; emptyText: string }) {
  return rows.length ? <div className="space-y-3">{rows.map(render)}</div> : <p className="text-slate-500">{emptyText}</p>;
}

function AppPage({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <div className="min-h-full bg-slate-50 p-8 text-slate-950">
      <div className="mb-6">
        <h1 className="text-3xl font-black tracking-tight">{title}</h1>
        <p className="mt-2 text-sm text-slate-500">{subtitle}</p>
      </div>
      {children}
    </div>
  );
}

function SidebarLink({ to, icon: Icon, children }: { to: string, icon: any, children: React.ReactNode }) {
  const location = useLocation();
  const isActive = location.pathname === to || (to === '/agents' && location.pathname === '/');
  return (
    <Link
      to={to}
      className={`flex min-h-10 items-center gap-3 rounded-md px-4 text-sm font-semibold transition ${
        isActive ? 'bg-slate-100 text-slate-950' : 'text-slate-700 hover:bg-slate-50 hover:text-slate-950'
      }`}
    >
      <Icon size={21} weight={isActive ? 'fill' : 'regular'} className="text-slate-600" /> {children}
    </Link>
  );
}

function Layout({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  return (
    <div className="flex h-screen min-w-[1180px] bg-slate-50 text-slate-950">
      <nav className="flex w-[210px] shrink-0 flex-col border-r border-slate-200 bg-white">
        <div className="border-b border-slate-200 p-5">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 bg-slate-50 font-bold">J</div>
              <div>
                <h2 className="font-bold leading-tight">Jettone</h2>
                <p className="text-sm text-blue-600">Active</p>
              </div>
            </div>
            <CaretUpDown size={18} className="text-slate-500" />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-3">
          <p className="mb-2 px-2 text-xs font-semibold text-slate-400">Platform</p>
          <div className="space-y-1">
            <SidebarLink to="/agents" icon={ListBullets}>Agent Setup</SidebarLink>
            <SidebarLink to="/logs" icon={ListBullets}>Call History</SidebarLink>
            <SidebarLink to="/numbers" icon={Hash}>My Numbers</SidebarLink>
            <SidebarLink to="/sip-trunks" icon={PhoneCall}>SIP Trunks</SidebarLink>
            <SidebarLink to="/knowledge-base" icon={Database}>Knowledge Base</SidebarLink>
            <SidebarLink to="/batches" icon={Stack}>Batches</SidebarLink>
            <SidebarLink to="/developers" icon={Code}>Developers</SidebarLink>
            <SidebarLink to="/providers" icon={PlugsConnected}>Providers</SidebarLink>
            <SidebarLink to="/workflows" icon={GitBranch}>Workflows</SidebarLink>
            <SidebarLink to="/campaigns" icon={ChartLineUp}>Campaigns</SidebarLink>
            <SidebarLink to="/documentation" icon={BookOpen}>Documentation</SidebarLink>
          </div>
          <p className="mb-2 mt-8 px-2 text-xs font-semibold text-slate-400">Team</p>
          <div className="space-y-1">
            <SidebarLink to="/admin" icon={Gear}>Workplace</SidebarLink>
            <SidebarLink to="/dashboard" icon={ChartLineUp}>Dashboard</SidebarLink>
            <SidebarLink to="/analytics" icon={ChartLineUp}>Analytics</SidebarLink>
            <SidebarLink to="/crm" icon={Users}>CRM Contacts</SidebarLink>
            <SidebarLink to="/billing" icon={CreditCard}>Billing</SidebarLink>
            <SidebarLink to="/settings" icon={ShieldCheck}>Settings</SidebarLink>
            <SidebarLink to="/terminal" icon={TerminalWindow}>Terminal Logs</SidebarLink>
          </div>
        </div>
        <div className="border-t border-slate-200 p-3">
          <button
            onClick={async () => {
              await clearAccessToken();
              navigate('/login');
            }}
            className="flex w-full items-center justify-between rounded-md bg-slate-50 px-3 py-3 text-sm font-semibold text-slate-900 hover:bg-slate-100"
          >
            <span className="flex items-center gap-2"><span className="flex h-7 w-7 items-center justify-center rounded-full bg-white text-xs shadow-sm">R</span> raghu@maxr.io</span>
            <CaretUpDown size={16} />
          </button>
        </div>
      </nav>
      <main className="flex-1 overflow-auto">
        {!isApiConfigured && (
          <div className="border-b border-amber-200 bg-amber-50 px-6 py-3 text-sm font-medium text-amber-900">
            {apiConnectionMessage}
          </div>
        )}
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
    const { data } = supabase.auth.onAuthStateChange((_event, session) => {
      setAuthenticated(Boolean(session?.access_token));
      setLoading(false);
    });
    return () => data.subscription.unsubscribe();
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
                  <Route path="/numbers" element={<ResourceList title="My Numbers" icon={Hash} emptyText="No phone numbers connected yet." />} />
                  <Route path="/sip-trunks" element={<ResourceList title="SIP Trunks" icon={PhoneCall} emptyText="No SIP trunks connected yet." />} />
                  <Route path="/knowledge-base" element={<ResourceList title="Knowledge Base" icon={Database} emptyText="No knowledge base sources uploaded yet." />} />
                  <Route path="/batches" element={<ResourceList title="Batches" icon={Stack} emptyText="No batches created yet." />} />
                  <Route path="/developers" element={<ResourceList title="Developers" icon={Code} emptyText="No developer keys or webhooks configured yet." />} />
                  <Route path="/providers" element={<ResourceList title="Providers" icon={PlugsConnected} emptyText="No voice or telephony providers configured yet." />} />
                  <Route path="/workflows" element={<ResourceList title="Workflows" icon={GitBranch} emptyText="No workflows created yet." />} />
                  <Route path="/campaigns" element={<Campaigns />} />
                  <Route path="/documentation" element={<ResourceList title="Documentation" icon={BookOpen} emptyText="No documentation pages connected yet." />} />
                  <Route path="/analytics" element={<Analytics />} />
                  <Route path="/crm" element={<Crm />} />
                  <Route path="/billing" element={<Billing />} />
                  <Route path="/settings" element={<Settings />} />
                  <Route path="/admin" element={<Admin />} />
                  <Route path="*" element={<Navigate to="/agents" replace />} />
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
