import { useEffect, useRef, useState } from 'react';
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
import type { Icon } from '@phosphor-icons/react';
import VoiceTester from './VoiceTester';
import TerminalPage from './Terminal';
import Login from './Login';
import { clearAccessToken, getAccessToken } from './auth';
import {
  api,
  apiConnectionMessage,
  apiUnreachableMessage,
  formatCallTestFailureMessage,
  SESSION_EXPIRED_EVENT,
  sessionExpiredMessage,
  isApiConfigured,
  type AgentRow,
  type AnalyticsSummary,
  type ProviderOptionsResponse,
  type BillingSummary,
  type Campaign,
  type ContactRow,
  type CurrentUser,
  type OpsReadiness,
  type PromptAssistAction,
  type WorkspaceSummary,
} from './lib/api';
import { isSupabaseConfigured, missingSupabaseEnvMessage, supabase } from './lib/supabase';
import { EmptyWell, InlineBanner, PageLoading, Spinner } from './components/UiFeedback';
import { ShellButton } from './components/ShellButton';
import CallLogDetail from './CallLogDetail';
import CallLogsPage from './CallLogsPage';
import ConfigCheck from './pages/ConfigCheck';
import heroAsset from './assets/hero.png';
import './App.css';

type HealthPayload = {
  supabase_configured?: boolean;
  livekit_configured?: boolean;
  service_role_key_present?: boolean;
  status?: string;
};

function getErrorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

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
        <nav className="relative z-10 mx-auto flex w-full max-w-7xl flex-col gap-5 px-4 py-5 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between sm:gap-y-4 sm:px-6">
          <Link to="/" className="flex shrink-0 items-center gap-3" aria-label="Jettone home">
            <JettoneLogo />
            <span>
              <span className="block text-lg font-black leading-none">Jettone</span>
              <span className="hidden text-xs text-cyan-100/70 sm:block">Consumer voice agents</span>
            </span>
          </Link>
          <div className="flex flex-1 flex-wrap justify-center gap-x-6 gap-y-2 text-sm text-slate-300 sm:flex-none sm:text-sm">
            <a href="#platform" className="rounded-md hover:text-white">
              Platform
            </a>
            <a href="#consumer" className="rounded-md hover:text-white">
              B2C workflows
            </a>
            <a href="#integrations" className="rounded-md hover:text-white">
              Stack
            </a>
          </div>
          <div className="flex shrink-0 items-center justify-end gap-2 sm:gap-3">
            <Link to="/login" className="rounded-lg px-4 py-2 text-sm font-semibold text-slate-200 hover:bg-white/10">
              Login
            </Link>
            <Link
              to="/login"
              className="inline-flex min-h-10 items-center justify-center rounded-lg bg-cyan-300 px-4 py-2 text-sm font-bold text-slate-950 shadow-lg shadow-cyan-950/30 hover:bg-cyan-200"
            >
              Launch agent
            </Link>
          </div>
        </nav>

        <div className="relative z-10 mx-auto grid min-h-[calc(92svh-120px)] w-full max-w-7xl items-center gap-8 px-4 pb-11 pt-3 sm:px-6 sm:pt-4 lg:min-h-[calc(92svh-82px)] lg:grid-cols-[1fr_0.95fr] lg:gap-10">
          <div className="max-w-3xl" data-reveal>
            <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-cyan-300/25 bg-cyan-300/10 px-3 py-1 text-sm text-cyan-100">
              <Sparkle size={16} weight="fill" />
              Billion-dollar voice layer for consumer brands
            </div>
            <h1 className="max-w-4xl text-4xl font-black leading-[1.05] tracking-normal text-white sm:text-6xl lg:text-7xl">
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
            <div className="mt-10 grid max-w-2xl grid-cols-1 gap-6 sm:grid-cols-3 sm:gap-3">
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
  description?: string;
  defaultLanguage?: string;
  versionId?: string;
  versionNumber?: number;
  versionStatus?: string;
  publishedAgentUuid?: string;
  llmProvider?: string;
  llmModel?: string;
  ttsProvider?: string;
  ttsModel?: string;
  ttsVoice?: string;
  ttsLanguage?: string;
  sttProvider?: string;
  sttModel?: string;
  sttLanguage?: string;
  voicePipeline?: string;
  /** Persisted agent row config (merge on save) */
  configSnapshot?: Record<string, unknown>;
  /** STT endpointing delay in seconds (engine_config) */
  sttMinEndpointingDelay?: number;
  maxTurns?: number;
  silenceTimeoutSeconds?: number;
  interruptionWords?: string;
  responseLatencyMode?: string;
  vertical?: string;
  languageConfig?: {
    language?: string;
    style?: string;
    tone?: string;
    formality?: string;
  };
  /** Call policy (call_config) */
  finalCallMessage?: string;
  silenceHangupEnabled?: boolean;
  silenceHangupSeconds?: number;
  totalCallTimeoutSeconds?: number;
  warmTransferEnabled?: boolean;
  transferDestinationE164?: string;
  callRetryEnabled?: boolean;
  callMaxRetries?: number;
  toolsConfig?: Array<{ id: string; enabled: boolean }>;
  analyticsTrackSummaries?: boolean;
  analyticsTrackProviderUsage?: boolean;
  inboundNumberId?: string;
  inboundAssignEnabled?: boolean;
  /** Optional — persisted in engine_config for AI Edit context */
  agentTone?: string;
  businessType?: string;
  dirty?: boolean;
  localOnly?: boolean;
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
    defaultLanguage: 'tamil_tanglish',
    ttsProvider: 'sarvam',
    ttsModel: 'bulbul:v3',
    ttsVoice: 'kavya',
    ttsLanguage: 'ta-IN',
    sttProvider: 'sarvam',
    sttModel: 'saaras:v3',
    sttLanguage: 'ta-IN',
    vertical: 'tamil_real_estate',
    languageConfig: {
      language: 'ta-IN',
      style: 'Tanglish',
      tone: 'warm',
      formality: 'conversational',
    },
    localOnly: true,
  },
  {
    id: 'real-estate-sales-agent',
    name: 'real estate sales agent',
    status: 'Active',
    phone: '+919876543210',
    welcomeMessage: 'Hi, thanks for calling Keystone Real Estate. I can help you with property details, pricing, and site visits.',
    prompt:
      'You are a professional real estate sales assistant. Qualify buyer intent, collect location and budget, answer common questions, and book a site visit.',
    localOnly: true,
  },
  {
    id: 'my-new-agent',
    name: 'My New Agent',
    status: 'Draft',
    phone: '+910000000000',
    welcomeMessage: 'Hello, thanks for calling. How can I help you today?',
    prompt: 'You are a helpful voice agent. Keep replies short, natural, and useful.',
    localOnly: true,
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

function AppPanel({ title, icon: IconComponent, children, action }: { title: string; icon?: Icon; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between gap-4">
        <h2 className="flex items-center gap-2 text-lg font-bold text-slate-950">
          {IconComponent && <IconComponent size={19} className="text-slate-400" />}
          {title}
          <Info size={16} className="text-slate-400" />
        </h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function configValue(config: Record<string, unknown> | undefined, key: string, fallback = '') {
  const value = config?.[key];
  return typeof value === 'string' ? value : fallback;
}

/** Treat empty / whitespace as missing so bad DB rows still get sane defaults */
function configString(config: Record<string, unknown> | undefined, key: string, fallback = '') {
  const value = config?.[key];
  if (typeof value === 'string' && value.trim()) return value.trim();
  return fallback;
}

const DEFAULT_TTS_MODEL = 'bulbul:v3';
const DEFAULT_STT_MODEL_SARVAM = 'saaras:v3';
const DEFAULT_STT_MODEL_DEEPGRAM = 'nova-2-general';

function defaultTtsLanguageForProfile(profile: string): string {
  if (profile === 'tamil' || profile === 'tamil_tanglish') return 'ta-IN';
  if (profile === 'english') return 'en-IN';
  return 'hi-IN';
}

function validateAudioForSave(agent: DemoAgent, deepgramConfigured: boolean | undefined): string | null {
  const ttp = (agent.ttsProvider || 'sarvam').toLowerCase();
  const stp = (agent.sttProvider || 'sarvam').toLowerCase();
  if (ttp === 'sarvam') {
    if (!(agent.ttsVoice || '').trim()) return 'TTS voice is required for Sarvam.';
    if (!(agent.ttsModel || '').trim()) return 'TTS model is required for Sarvam.';
  }
  if (ttp === 'elevenlabs') {
    if (!(agent.ttsVoice || '').trim()) return 'TTS voice is required for ElevenLabs.';
  }
  if (stp === 'sarvam' && !(agent.sttModel || '').trim()) {
    return 'STT model is required for Sarvam Saaras.';
  }
  if (stp === 'deepgram' && !deepgramConfigured) {
    return 'Deepgram is not configured on the server (DEEPGRAM_API_KEY). Choose Sarvam STT or set the key in Railway.';
  }
  return null;
}

function configNum(cfg: Record<string, unknown> | undefined, key: string, fallback: number): number {
  const v = cfg?.[key];
  if (typeof v === 'number' && !Number.isNaN(v)) return v;
  if (typeof v === 'string' && v.trim() && !Number.isNaN(Number(v))) return Number(v);
  return fallback;
}

function configBool(cfg: Record<string, unknown> | undefined, key: string, fallback: boolean): boolean {
  const v = cfg?.[key];
  if (typeof v === 'boolean') return v;
  return fallback;
}

function parseInterruptionWords(raw: unknown): string {
  if (Array.isArray(raw)) return raw.filter((x): x is string => typeof x === 'string').join(', ');
  if (typeof raw === 'string') return raw;
  return '';
}

function serializeInterruptionWords(s: string): string[] {
  return s.split(/[,;\n]+/).map((w) => w.trim()).filter(Boolean);
}

const DEFAULT_TOOLS: Array<{ id: string; enabled: boolean }> = [
  { id: 'check_availability', enabled: true },
  { id: 'save_booking_intent', enabled: true },
  { id: 'transfer_call', enabled: true },
  { id: 'custom_function', enabled: false },
];

function normalizeToolsConfig(raw: unknown): Array<{ id: string; enabled: boolean }> {
  if (!Array.isArray(raw)) return DEFAULT_TOOLS.map((t) => ({ ...t }));
  const m = new Map<string, boolean>();
  for (const item of raw) {
    if (item && typeof item === 'object' && 'id' in item) {
      const id = String((item as { id: string }).id);
      m.set(id, Boolean((item as { enabled?: boolean }).enabled));
    }
  }
  return DEFAULT_TOOLS.map((d) => ({ id: d.id, enabled: m.has(d.id) ? Boolean(m.get(d.id)) : d.enabled }));
}

function isE164Like(s: string): boolean {
  const x = s.replace(/\s/g, '');
  return /^\+[1-9]\d{7,14}$/.test(x);
}

function validateAgentForSave(agent: DemoAgent, deepgramConfigured: boolean | undefined): string | null {
  const audioErr = validateAudioForSave(agent, deepgramConfigured);
  if (audioErr) return audioErr;
  const tools = agent.toolsConfig || normalizeToolsConfig(undefined);
  const transferOn = tools.find((t) => t.id === 'transfer_call')?.enabled;
  if (transferOn) {
    const dest = (agent.transferDestinationE164 || '').trim() || (agent.phone || '').trim();
    if (!isE164Like(dest)) {
      return 'Transfer tool requires a valid E.164 destination (Call tab) or agent phone.';
    }
  }
  if (agent.inboundAssignEnabled && !(agent.inboundNumberId || '').trim()) {
    return 'Inbound assignment requires an inbound number or resource id.';
  }
  return null;
}

function validateAgentForPublish(agent: DemoAgent, deepgramConfigured: boolean | undefined): string | null {
  if (!(agent.welcomeMessage || '').trim()) return 'Welcome message is required before publishing.';
  if (!(agent.prompt || '').trim()) return 'Agent prompt is required before publishing.';
  const audioErr = validateAgentForSave(agent, deepgramConfigured);
  if (audioErr) return audioErr;
  if (!(agent.ttsProvider || '').trim() || !(agent.sttProvider || '').trim()) {
    return 'Voice config is required before publishing.';
  }
  if (!(agent.llmProvider || '').trim() || !(agent.voicePipeline || 'livekit_agents').trim()) {
    return 'Pipeline config is required before publishing.';
  }
  return null;
}

function mapAgentRow(row: AgentRow, index = 0): DemoAgent {
  const version = row.active_version;
  const llmConfig = version?.llm_config;
  const audioConfig = version?.audio_config;
  const engineConfig = version?.engine_config as Record<string, unknown> | undefined;
  const callConfig = version?.call_config as Record<string, unknown> | undefined;
  const analyticsConfig = version?.analytics_config as Record<string, unknown> | undefined;
  const rowConfig = row.config as Record<string, unknown> | undefined;
  const status = version?.status === 'published' ? 'published' : (row.status || version?.status || 'draft');
  const publishedAgentUuid =
    version?.status === 'published'
      ? String(row.published_agent_uuid || row.id || '').trim() || undefined
      : undefined;
  const defaultLanguage =
    row.default_language ||
    configString(engineConfig, 'language_profile', 'multilingual');
  const ttsLanguage =
    configString(audioConfig, 'tts_language', '') || defaultTtsLanguageForProfile(defaultLanguage);
  const snap =
    rowConfig && typeof rowConfig === 'object'
      ? { ...rowConfig }
      : ({} as Record<string, unknown>);
  return {
    id: row.id || `agent-${index}`,
    name: row.name || row.config?.name || `Agent ${index + 1}`,
    description: row.description || '',
    status,
    phone: row.phone || row.config?.phone || '+918065480786',
    welcomeMessage: version?.welcome_message || row.config?.welcomeMessage || row.config?.first_line || demoAgents[0].welcomeMessage,
    prompt: version?.system_prompt || row.config?.prompt || row.config?.agent_instructions || demoAgents[0].prompt,
    defaultLanguage,
    versionId: version?.id || row.active_version_id,
    versionNumber: version?.version,
    versionStatus: version?.status || 'draft',
    publishedAgentUuid,
    llmProvider: configString(llmConfig, 'provider', 'groq'),
    llmModel: configString(llmConfig, 'model', 'llama-3.3-70b-versatile'),
    ttsProvider: configString(audioConfig, 'tts_provider', 'sarvam'),
    ttsModel: configString(audioConfig, 'tts_model', DEFAULT_TTS_MODEL),
    ttsVoice: configString(audioConfig, 'tts_voice', 'kavya'),
    ttsLanguage,
    sttProvider: configString(audioConfig, 'stt_provider', 'sarvam'),
    sttModel: configString(audioConfig, 'stt_model', DEFAULT_STT_MODEL_SARVAM),
    sttLanguage: configString(audioConfig, 'stt_language', 'unknown'),
    voicePipeline: configString(rowConfig, 'voice_pipeline', configString(engineConfig, 'voice_pipeline', 'livekit_agents')),
    agentTone: configString(engineConfig, 'agent_tone', ''),
    businessType: configString(engineConfig, 'business_type', ''),
    vertical: configString(engineConfig, 'vertical', ''),
    languageConfig: {
      language: configString(engineConfig?.language_config as Record<string, unknown> | undefined, 'language', ''),
      style: configString(engineConfig?.language_config as Record<string, unknown> | undefined, 'style', ''),
      tone: configString(engineConfig?.language_config as Record<string, unknown> | undefined, 'tone', ''),
      formality: configString(engineConfig?.language_config as Record<string, unknown> | undefined, 'formality', ''),
    },
    configSnapshot: snap,
    sttMinEndpointingDelay: configNum(engineConfig, 'stt_min_endpointing_delay', 0.05),
    maxTurns: configNum(engineConfig, 'max_turns', 14),
    silenceTimeoutSeconds: configNum(engineConfig, 'silence_timeout_seconds', 45),
    interruptionWords: parseInterruptionWords(engineConfig?.interruption_words),
    responseLatencyMode: configString(engineConfig, 'response_latency_mode', 'normal'),
    finalCallMessage: configString(callConfig, 'final_call_message', ''),
    silenceHangupEnabled: configBool(callConfig, 'silence_hangup_enabled', true),
    silenceHangupSeconds: configNum(callConfig, 'silence_hangup_seconds', 45),
    totalCallTimeoutSeconds: configNum(callConfig, 'total_call_timeout_seconds', 0),
    warmTransferEnabled: configBool(callConfig, 'warm_transfer_enabled', true),
    transferDestinationE164: configString(callConfig, 'transfer_destination_e164', ''),
    callRetryEnabled: configBool(callConfig, 'retry_enabled', true),
    callMaxRetries: configNum(callConfig, 'max_retries', 3),
    toolsConfig: normalizeToolsConfig(version?.tools_config),
    analyticsTrackSummaries: configBool(analyticsConfig, 'track_call_summaries', true),
    analyticsTrackProviderUsage: configBool(analyticsConfig, 'track_provider_usage', true),
    inboundNumberId: configString(rowConfig, 'inbound_number_id', ''),
    inboundAssignEnabled: configBool(rowConfig, 'inbound_assign_enabled', false),
  };
}

function agentConfigPayload(agent: DemoAgent): Record<string, unknown> {
  return {
    ...(agent.configSnapshot || {}),
    phone: agent.phone,
    inbound_number_id: (agent.inboundNumberId || '').trim(),
    inbound_assign_enabled: agent.inboundAssignEnabled ?? false,
    voice_pipeline: agent.voicePipeline || 'livekit_agents',
  };
}

function versionPayload(agent: DemoAgent) {
  const defaultLanguage = agent.defaultLanguage || 'multilingual';
  const ttsLang = (agent.ttsLanguage && agent.ttsLanguage.trim()) || defaultTtsLanguageForProfile(defaultLanguage);
  const languageConfig = {
    language: (agent.languageConfig?.language || (defaultLanguage === 'tamil_tanglish' || defaultLanguage === 'tamil' ? 'ta-IN' : ttsLang)).trim(),
    style: (agent.languageConfig?.style || (defaultLanguage === 'tamil_tanglish' ? 'Tanglish' : defaultLanguage)).trim(),
    tone: (agent.languageConfig?.tone || agent.agentTone || 'warm').trim(),
    formality: (agent.languageConfig?.formality || 'conversational').trim(),
  };
  const ttsModel = (agent.ttsModel && agent.ttsModel.trim()) || DEFAULT_TTS_MODEL;
  const stp = (agent.sttProvider || 'sarvam').toLowerCase();
  const sttModel =
    (agent.sttModel && agent.sttModel.trim()) ||
    (stp === 'deepgram' ? DEFAULT_STT_MODEL_DEEPGRAM : DEFAULT_STT_MODEL_SARVAM);
  const endpointDelay = agent.sttMinEndpointingDelay ?? 0.05;
  const maxTurnsV = agent.maxTurns ?? 14;
  const silenceEngineV = agent.silenceTimeoutSeconds ?? 45;
  return {
    welcome_message: agent.welcomeMessage,
    system_prompt: agent.prompt,
    llm_config: {
      provider: agent.llmProvider || 'groq',
      model: agent.llmModel || 'llama-3.3-70b-versatile',
      temperature: 0.4,
      max_tokens: 64,
      fallback_providers: ['openai'],
    },
    audio_config: {
      tts_provider: agent.ttsProvider || 'sarvam',
      tts_model: ttsModel,
      tts_voice: (agent.ttsVoice && agent.ttsVoice.trim()) || 'kavya',
      tts_language: ttsLang,
      stt_provider: agent.sttProvider || 'sarvam',
      stt_model: sttModel,
      stt_language: agent.sttLanguage || 'unknown',
      noise_suppression: true,
    },
    engine_config: {
      language_profile: defaultLanguage,
      agent_tone: (agent.agentTone || '').trim(),
      business_type: (agent.businessType || '').trim(),
      vertical: (agent.vertical || (defaultLanguage === 'tamil_tanglish' ? 'tamil_real_estate' : '')).trim(),
      language_config: languageConfig,
      stt_min_endpointing_delay: endpointDelay,
      max_turns: maxTurnsV,
      silence_timeout_seconds: silenceEngineV,
      interruption_words: serializeInterruptionWords(agent.interruptionWords || ''),
      response_latency_mode: agent.responseLatencyMode || 'normal',
      voice_pipeline: agent.voicePipeline || 'livekit_agents',
    },
    call_config: {
      final_call_message: agent.finalCallMessage || '',
      silence_hangup_enabled: agent.silenceHangupEnabled ?? true,
      silence_hangup_seconds: agent.silenceHangupSeconds ?? 45,
      total_call_timeout_seconds: agent.totalCallTimeoutSeconds ?? 0,
      warm_transfer_enabled: agent.warmTransferEnabled ?? true,
      transfer_destination_e164: (agent.transferDestinationE164 || '').trim(),
      retry_enabled: agent.callRetryEnabled ?? true,
      max_retries: agent.callMaxRetries ?? 3,
    },
    tools_config: normalizeToolsConfig(agent.toolsConfig),
    analytics_config: {
      track_call_summaries: agent.analyticsTrackSummaries ?? true,
      track_provider_usage: agent.analyticsTrackProviderUsage ?? true,
    },
  };
}

function Agents() {
  const [agents, setAgents] = useState<DemoAgent[]>(() => (isApiConfigured ? [] : demoAgents));
  const [selectedId, setSelectedId] = useState(() => (!isApiConfigured ? demoAgents[0].id : ''));
  const [search, setSearch] = useState('');
  const [activeTab, setActiveTab] = useState('Agent');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [formStatus, setFormStatus] = useState<{ tone: 'success' | 'error' | 'info'; message: string } | null>(null);
  const [callBusy, setCallBusy] = useState<'browser' | 'phone' | 'sip' | null>(null);
  const [callStatus, setCallStatus] = useState<{ tone: 'success' | 'error'; message: string } | null>(null);
  const [sipTestReady, setSipTestReady] = useState(false);
  const [providerOpts, setProviderOpts] = useState<ProviderOptionsResponse | null>(null);
  const [aiEditOpen, setAiEditOpen] = useState(false);
  const [aiEditAction, setAiEditAction] = useState<PromptAssistAction>('improve');
  const [aiEditLoading, setAiEditLoading] = useState(false);

  useEffect(() => {
    if (!isApiConfigured) return;
    let cancelled = false;
    (async () => {
      try {
        const opts = await api.providerOptions();
        if (!cancelled) setProviderOpts(opts);
      } catch {
        if (!cancelled) setProviderOpts(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!isApiConfigured) return;
    (async () => {
      try {
        const [sip, lk] = await Promise.all([api.sipHealth(), api.livekitHealth()]);
        setSipTestReady(Boolean(sip.ok && lk.ok && lk.api_reachable));
      } catch {
        setSipTestReady(false);
      }
    })();
  }, []);

  useEffect(() => {
    if (!isApiConfigured) return;
    (async () => {
      setLoading(true);
      setFormStatus(null);
      try {
        const rows = await api.agents();
        if (!rows.length) {
          setAgents([]);
          setSelectedId('');
          setFormStatus(null);
          return;
        }
        const mapped = rows.map(mapAgentRow);
        setAgents(mapped);
        setSelectedId(mapped[0]?.id || '');
      } catch (error: unknown) {
        setFormStatus({ tone: 'error', message: getErrorMessage(error, 'Failed to load agents.') });
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const createAgent = async () => {
    setSaving(true);
    setFormStatus(null);
    try {
      const created = await api.createAgent({
        name: 'Tamil Real Estate Agent',
        description: 'Draft Tamil real-estate agent for first production testing.',
        default_language: 'tamil_tanglish',
        config: { phone: '+918065480786' },
        ...versionPayload({
          ...demoAgents[0],
          id: '',
          name: 'Tamil Real Estate Agent',
          localOnly: false,
        }),
      });
      const mapped = mapAgentRow(created);
      setAgents((current) => [mapped, ...current.filter((agent) => !agent.localOnly)]);
      setSelectedId(mapped.id);
      setFormStatus({ tone: 'success', message: 'Draft agent created. Edit it, save, then publish before calling.' });
    } catch (error: unknown) {
      setFormStatus({ tone: 'error', message: getErrorMessage(error, 'Agent create failed.') });
    } finally {
      setSaving(false);
    }
  };

  if (isApiConfigured && loading) {
    return (
      <div className="min-h-full min-w-0 bg-slate-50 px-4 py-4 sm:px-6">
        <p className="mb-5 text-sm text-slate-600">Fine tune your agents</p>
        <PageLoading message="Loading agents…" />
      </div>
    );
  }

  if (isApiConfigured && !loading && agents.length === 0) {
    return (
      <div className="min-h-full min-w-0 bg-slate-50 px-4 py-4 sm:px-6">
        <p className="mb-5 text-sm text-slate-600">Fine tune your agents</p>
        <EmptyWell
          title="No agents yet"
          description="Create your first voice agent, then publish it before placing test calls. Published agents unlock browser and SIP tests."
        >
          <ShellButton primary onClick={createAgent} disabled={saving}>
            {saving ? (
              <>
                <Spinner className="h-4 w-4 text-white" label="Creating agent" /> Working…
              </>
            ) : (
              <>
                <Plus size={18} /> New Agent
              </>
            )}
          </ShellButton>
          <Link to="/dashboard">
            <ShellButton>Open dashboard</ShellButton>
          </Link>
        </EmptyWell>
        {formStatus?.tone === 'error' ? (
          <div className="mt-6">
            <InlineBanner tone="error">{formStatus.message}</InlineBanner>
          </div>
        ) : null}
      </div>
    );
  }

  const selected = agents.find((agent) => agent.id === selectedId) ?? agents[0]!;
  const selectedIsPublished = selected.versionStatus === 'published';
  const selectedIsDbBacked = !selected.localOnly && selected.id.length > 20;
  const selectedCanCall = selectedIsDbBacked && selectedIsPublished && Boolean(selected.publishedAgentUuid);
  const filtered = agents.filter((agent) => agent.name.toLowerCase().includes(search.toLowerCase()));
  const llmModels =
    providerOpts?.llm_providers?.find((p) => p.id === (selected.llmProvider || 'groq'))?.models ||
    ['llama-3.3-70b-versatile', 'llama-3.1-8b-instant'];
  const ttsModelChoices = providerOpts?.tts_models?.[selected.ttsProvider || 'sarvam'] || [DEFAULT_TTS_MODEL];
  const sttModelChoices =
    providerOpts?.stt_models?.[selected.sttProvider || 'sarvam'] ||
    (selected.sttProvider === 'deepgram'
      ? [DEFAULT_STT_MODEL_DEEPGRAM, 'nova-3-general']
      : [DEFAULT_STT_MODEL_SARVAM]);
  const sttProviderRows = (providerOpts?.stt_providers || []).filter(
    (p) => p.id !== 'deepgram' || providerOpts?.deepgram_configured,
  );
  const ttsVoices =
    providerOpts?.tts_providers?.find((p) => p.id === (selected.ttsProvider || 'sarvam'))?.voices ||
    ['kavya', 'ritu', 'priya', 'dev', 'rohan'];
  const langProfiles = providerOpts?.language_profiles || [];
  const browserTestBlockReason =
    !isApiConfigured
      ? apiConnectionMessage
      : validateAudioForSave(selected, providerOpts?.deepgram_configured) ||
        (!selectedCanCall ? 'Please Save and Publish the agent before testing.' : null);
  const updateSelected = (fields: Partial<DemoAgent>) => {
    setFormStatus(null);
    setAgents((current) => current.map((agent) => (agent.id === selected.id ? { ...agent, ...fields, dirty: true } : agent)));
  };
  const refreshAgent = async (agentId: string) => {
    const row = await api.agent(agentId);
    const mapped = mapAgentRow(row);
    setAgents((current) => current.map((agent) => (agent.id === agentId ? mapped : agent)));
    setSelectedId(mapped.id);
    return mapped;
  };
  const saveAgent = async () => {
    const audioErr = validateAgentForSave(selected, providerOpts?.deepgram_configured);
    if (audioErr) {
      setFormStatus({ tone: 'error', message: audioErr });
      return;
    }
    setSaving(true);
    setFormStatus(null);
    try {
      if (!(await getAccessToken())) {
        throw new Error('Please login again before saving or publishing.');
      }
      if (!selectedIsDbBacked) {
        const created = await api.createAgent({
          name: selected.name,
          description: selected.description || '',
          default_language: selected.defaultLanguage || 'multilingual',
          config: agentConfigPayload(selected),
          ...versionPayload(selected),
        });
        const mapped = mapAgentRow(created);
        setAgents((current) => [mapped, ...current.filter((agent) => agent.id !== selected.id)]);
        setSelectedId(mapped.id);
        setFormStatus({ tone: 'info', message: 'Saved but not published. Changes are not live until you click Publish.' });
        return;
      }
      await api.updateAgent(selected.id, {
        name: selected.name,
        description: selected.description || '',
        default_language: selected.defaultLanguage || 'multilingual',
        config: agentConfigPayload(selected),
      });
      if (!selected.versionId || selected.versionStatus === 'published') {
        await api.createAgentVersion(selected.id, versionPayload(selected));
        await refreshAgent(selected.id);
        setFormStatus({ tone: 'info', message: 'Saved but not published. Changes are not live until you click Publish.' });
      } else {
        await api.updateAgentVersion(selected.id, selected.versionId, versionPayload(selected));
        await refreshAgent(selected.id);
        setFormStatus({ tone: 'info', message: 'Saved but not published. Changes are not live until you click Publish.' });
      }
    } catch (error: unknown) {
      setFormStatus({ tone: 'error', message: getErrorMessage(error, 'Agent save failed.') });
    } finally {
      setSaving(false);
    }
  };
  const publishAgent = async () => {
    const publishErr = validateAgentForPublish(selected, providerOpts?.deepgram_configured);
    if (publishErr) {
      setFormStatus({ tone: 'error', message: publishErr });
      return;
    }
    setPublishing(true);
    setFormStatus(null);
    try {
      if (!(await getAccessToken())) {
        throw new Error('Please login again before saving or publishing.');
      }
      let agentId = selected.id;
      let versionId = selected.versionId;
      if (!selectedIsDbBacked) {
        const created = await api.createAgent({
          name: selected.name,
          description: selected.description || '',
          default_language: selected.defaultLanguage || 'multilingual',
          config: agentConfigPayload(selected),
          ...versionPayload(selected),
        });
        const mapped = mapAgentRow(created);
        agentId = mapped.id;
        versionId = mapped.versionId;
        setAgents((current) => [mapped, ...current.filter((agent) => agent.id !== selected.id)]);
        setSelectedId(mapped.id);
      } else {
        await api.updateAgent(selected.id, {
          name: selected.name,
          description: selected.description || '',
          default_language: selected.defaultLanguage || 'multilingual',
          config: agentConfigPayload(selected),
        });
        if (selected.dirty || selected.versionStatus === 'published' || !versionId) {
          const draft = await api.createAgentVersion(selected.id, versionPayload(selected));
          versionId = draft.id;
        } else if (versionId) {
          await api.updateAgentVersion(selected.id, versionId, versionPayload(selected));
        }
      }
      if (!agentId || !versionId) {
        throw new Error('Save the agent first, then publish the draft version.');
      }
      const result = await api.publishAgentVersion(agentId, versionId);
      const mapped = mapAgentRow(result.agent);
      setAgents((current) => current.map((item) => (item.id === mapped.id || item.id === selected.id ? mapped : item)));
      setSelectedId(mapped.id);
      setFormStatus({ tone: 'success', message: `Published. Live calls now use this prompt and welcome message. UUID ${mapped.publishedAgentUuid || 'pending'}.` });
    } catch (error: unknown) {
      setFormStatus({ tone: 'error', message: getErrorMessage(error, 'Agent publish failed.') });
    } finally {
      setPublishing(false);
    }
  };
  const runBrowserTest = async () => {
    if (!selectedCanCall) {
      setCallStatus({ tone: 'error', message: 'Please Save and Publish the agent before testing.' });
      return;
    }
    const audioErr = validateAudioForSave(selected, providerOpts?.deepgram_configured);
    if (audioErr) {
      setCallStatus({ tone: 'error', message: audioErr });
      return;
    }
    setCallBusy('browser');
    setCallStatus(null);
    try {
      const result = await api.browserTest(selected.publishedAgentUuid);
      setCallStatus({
        tone: 'success',
        message: `Browser test ready in room ${result.roomName}. agent_version_id=${result.agent_version_id || selected.versionId || 'pending'}`,
      });
    } catch (error: unknown) {
      setCallStatus({ tone: 'error', message: formatCallTestFailureMessage(error) });
    } finally {
      setCallBusy(null);
    }
  };
  const runPhoneCall = async () => {
    if (!selectedCanCall) {
      setCallStatus({ tone: 'error', message: 'Please Save and Publish the agent before testing.' });
      return;
    }
    const audioErr = validateAudioForSave(selected, providerOpts?.deepgram_configured);
    if (audioErr) {
      setCallStatus({ tone: 'error', message: audioErr });
      return;
    }
    setCallBusy('phone');
    setCallStatus(null);
    try {
      const result = await api.outboundCall(selected.phone, selected.publishedAgentUuid);
      setCallStatus({
        tone: 'success',
        message: `Outbound call dispatched to ${result.phone_number} in room ${result.room_name}. agent_version_id=${result.agent_version_id || selected.versionId || 'pending'}`,
      });
    } catch (error: unknown) {
      setCallStatus({ tone: 'error', message: formatCallTestFailureMessage(error) });
    } finally {
      setCallBusy(null);
    }
  };
  const runSipTestCall = async () => {
    if (!selectedCanCall) {
      setCallStatus({ tone: 'error', message: 'Please Save and Publish the agent before testing.' });
      return;
    }
    const audioErr = validateAudioForSave(selected, providerOpts?.deepgram_configured);
    if (audioErr) {
      setCallStatus({ tone: 'error', message: audioErr });
      return;
    }
    setCallBusy('sip');
    setCallStatus(null);
    try {
      const result = await api.sipTestCall(selected.phone, selected.publishedAgentUuid);
      setCallStatus({
        tone: 'success',
        message: `SIP test succeeded — room ${result.room_name}, callee ${result.phone_number_masked}, ${result.sip_status}.`,
      });
    } catch (error: unknown) {
      setCallStatus({ tone: 'error', message: formatCallTestFailureMessage(error) });
    } finally {
      setCallBusy(null);
    }
  };

  const runPromptAssist = async () => {
    if (!isApiConfigured) {
      setFormStatus({ tone: 'error', message: apiConnectionMessage });
      return;
    }
    setAiEditLoading(true);
    try {
      const langList = langProfiles.length
        ? langProfiles
        : [
            { id: 'multilingual', label: 'Multilingual Auto' },
            { id: 'english', label: 'English' },
            { id: 'hindi', label: 'Hindi' },
            { id: 'tamil', label: 'Tamil' },
            { id: 'tamil_tanglish', label: 'Tamil / Tanglish' },
          ];
      const langLabel =
        langList.find((p) => p.id === (selected.defaultLanguage || 'multilingual'))?.label || selected.defaultLanguage || '';
      const result = await api.promptAssist({
        current_prompt: selected.prompt,
        action: aiEditAction,
        language_profile: selected.defaultLanguage || 'multilingual',
        language_profile_label: langLabel,
        tone: selected.agentTone?.trim() || undefined,
        business_type: selected.businessType?.trim() || undefined,
      });
      updateSelected({ prompt: result.prompt });
      setFormStatus({
        tone: 'success',
        message: `Prompt refined (${result.provider}). Save agent to persist this draft.`,
      });
      setAiEditOpen(false);
    } catch (error: unknown) {
      setFormStatus({ tone: 'error', message: getErrorMessage(error, 'AI Edit failed.') });
    } finally {
      setAiEditLoading(false);
    }
  };

  const applyTamilPrimaryLanguage = () => {
    updateSelected({
      defaultLanguage: 'tamil_tanglish',
      ttsLanguage: 'ta-IN',
      sttLanguage: 'unknown',
      vertical: 'tamil_real_estate',
      languageConfig: {
        language: 'ta-IN',
        style: 'Tanglish',
        tone: selected.agentTone?.trim() || 'warm',
        formality: 'conversational',
      },
    });
    setActiveTab('Audio');
    setFormStatus({
      tone: 'info',
      message: 'Tamil / Tanglish is now the primary language profile. Save agent, then publish to apply it to calls.',
    });
  };

  return (
    <>
    <div className="min-h-full min-w-0 bg-slate-50 px-4 py-4 sm:px-6">
      <p className="mb-5 text-sm text-slate-600">Fine tune your agents</p>
      <div className="flex min-h-[min(720px,calc(100dvh-4rem))] flex-col gap-4 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-xl shadow-slate-200/70 lg:grid lg:h-[calc(100dvh-56px)] lg:min-h-[720px] lg:grid-cols-[minmax(0,376px)_minmax(0,1fr)_minmax(0,280px)] lg:gap-0">
        <aside className="flex min-h-0 flex-col overflow-hidden border-slate-200 lg:border-r">
          <div className="border-b border-slate-200 p-5">
            <h1 className="mb-3 text-2xl font-black text-slate-950">Your Agents</h1>
            <div className="flex gap-3">
              <ShellButton><DownloadSimple size={18} /> Import</ShellButton>
              <ShellButton onClick={createAgent} disabled={saving}>
                <Plus size={18} />{' '}
                {saving ? (
                  <span className="inline-flex items-center gap-2">
                    <Spinner className="h-4 w-4" label="Creating" />
                    Working…
                  </span>
                ) : (
                  'New Agent'
                )}
              </ShellButton>
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
                <span className="block">{agent.name}</span>
                <span className={`mt-2 inline-flex rounded-full px-2 py-0.5 text-xs ${
                  agent.versionStatus === 'published' || agent.status === 'active'
                    ? 'bg-emerald-50 text-emerald-700'
                    : 'bg-amber-50 text-amber-700'
                }`}>
                  {agent.versionStatus === 'published' || agent.status === 'active' ? 'published' : 'draft'}
                </span>
              </button>
            ))}
          </div>
        </aside>

        <main className="min-h-0 flex-1 overflow-y-auto bg-white p-4 sm:p-5">
          <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
            <div className="grid gap-4 sm:grid-cols-[1fr_auto_auto] lg:grid-cols-[minmax(0,1fr)_auto_auto] lg:items-center lg:gap-7">
              <input
                value={selected.name}
                onChange={(event) => updateSelected({ name: event.target.value })}
                className="h-12 rounded-md border border-transparent bg-white text-4xl font-normal text-slate-950 outline-none shadow-sm focus:border-slate-200"
              />
              <ShellButton><Copy size={20} /> {selected.publishedAgentUuid || selected.id}</ShellButton>
              <ShellButton onClick={publishAgent} disabled={publishing || saving}>
                <ShareNetwork size={20} />{' '}
                {publishing ? (
                  <span className="inline-flex items-center gap-2">
                    <Spinner className="h-4 w-4" label="Publishing" />
                    Publishing…
                  </span>
                ) : (
                  'Publish'
                )}
              </ShellButton>
            </div>
            <div className="mt-4 grid gap-3 rounded-lg bg-slate-50 p-4 text-sm md:grid-cols-2">
              <p><span className="font-semibold text-slate-500">Agent status:</span> {selectedIsPublished ? 'published' : 'draft'}</p>
              <p><span className="font-semibold text-slate-500">Version:</span> {selected.versionNumber ? `v${selected.versionNumber}` : '-'} ({selected.versionStatus || 'draft'})</p>
              <p className="break-all"><span className="font-semibold text-slate-500">Published agent UUID:</span> {selected.publishedAgentUuid || 'Publish to generate call-ready UUID'}</p>
              <p className="break-all"><span className="font-semibold text-slate-500">agent_version_id:</span> {selected.versionId || '-'}</p>
            </div>
            {(!selectedIsPublished || selected.dirty) && (
              <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
                Changes are not live until you click Publish.
              </div>
            )}
            {formStatus && (
              <div className={`mt-4 rounded-md border px-3 py-2 text-sm ${
                formStatus.tone === 'success'
                  ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
                  : formStatus.tone === 'info'
                    ? 'border-blue-200 bg-blue-50 text-blue-800'
                    : 'border-red-200 bg-red-50 text-red-700'
              }`}>
                {formStatus.message}
              </div>
            )}
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

            <div className="my-5 grid grid-cols-2 gap-1 rounded-lg bg-slate-100 p-1 sm:grid-cols-4 lg:grid-cols-8">
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
                <label className="mb-4 block">
                  <span className="text-sm font-medium text-slate-600">Phone number for outbound proof</span>
                  <input
                    value={selected.phone}
                    onChange={(event) => updateSelected({ phone: event.target.value })}
                    placeholder="+919876543210"
                    className="mt-2 w-full rounded-md border border-slate-200 px-4 py-3 text-slate-950 outline-none focus:border-blue-400"
                  />
                </label>
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
                action={
                  <ShellButton
                    onClick={() => {
                      setAiEditOpen(true);
                      setFormStatus(null);
                    }}
                    disabled={aiEditLoading || !isApiConfigured}
                  >
                    <Gear size={17} /> AI Edit
                  </ShellButton>
                }
              >
                <div className="mb-5 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={applyTamilPrimaryLanguage}
                    className="rounded-md bg-blue-600 px-4 py-2 text-sm font-bold text-white"
                  >
                    Tamil (Primary)
                  </button>
                  <ShellButton onClick={applyTamilPrimaryLanguage}>
                    <Plus size={17} /> Add Language
                  </ShellButton>
                </div>
                <textarea
                  value={selected.prompt}
                  onChange={(event) => updateSelected({ prompt: event.target.value })}
                  className="h-72 w-full resize-none rounded-md border border-slate-200 bg-white p-4 text-lg leading-7 text-slate-950 outline-none focus:border-blue-400"
                />
              </AppPanel>
            </div>
          ) : activeTab === 'LLM' ? (
            <AppPanel title="LLM Settings" icon={Gear}>
              <div className="grid gap-4 md:grid-cols-2">
                <SelectField
                  label="LLM provider"
                  value={selected.llmProvider || 'groq'}
                  onChange={(v) => {
                    const models =
                      providerOpts?.llm_providers?.find((p) => p.id === v)?.models ||
                      ['llama-3.3-70b-versatile'];
                    updateSelected({ llmProvider: v, llmModel: models[0] });
                  }}
                >
                  {(providerOpts?.llm_providers || [
                    { id: 'groq', label: 'Groq' },
                    { id: 'openai', label: 'OpenAI' },
                  ]).map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.label || p.id}
                    </option>
                  ))}
                </SelectField>
                <SelectField label="LLM model" value={selected.llmModel || llmModels[0]} onChange={(v) => updateSelected({ llmModel: v })}>
                  {llmModels.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </SelectField>
              </div>
            </AppPanel>
          ) : activeTab === 'Audio' ? (
            <AppPanel title="Audio Settings" icon={Translate}>
              <div className="grid gap-4 md:grid-cols-2">
                <SelectField
                  label="TTS provider"
                  value={selected.ttsProvider || 'sarvam'}
                  onChange={(v) => {
                    const models = providerOpts?.tts_models?.[v] || [DEFAULT_TTS_MODEL];
                    const voices = providerOpts?.tts_providers?.find((p) => p.id === v)?.voices || ['kavya'];
                    const cur = selected.ttsVoice || '';
                    const nextVoice = voices.includes(cur) ? cur : voices[0];
                    updateSelected({
                      ttsProvider: v,
                      ttsModel: models[0],
                      ttsVoice: nextVoice,
                    });
                  }}
                >
                  {(providerOpts?.tts_providers || [{ id: 'sarvam', label: 'Sarvam AI' }]).map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.label || p.id}
                    </option>
                  ))}
                </SelectField>
                <SelectField label="TTS model" value={selected.ttsModel || DEFAULT_TTS_MODEL} onChange={(v) => updateSelected({ ttsModel: v })}>
                  {ttsModelChoices.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </SelectField>
                <SelectField label="TTS voice" value={selected.ttsVoice || 'kavya'} onChange={(v) => updateSelected({ ttsVoice: v })}>
                  {ttsVoices.map((v) => (
                    <option key={v} value={v}>
                      {v}
                    </option>
                  ))}
                </SelectField>
                <SelectField
                  label="TTS language (BCP-47)"
                  value={selected.ttsLanguage || defaultTtsLanguageForProfile(selected.defaultLanguage || 'multilingual')}
                  onChange={(v) => updateSelected({ ttsLanguage: v })}
                >
                  {['en-IN', 'hi-IN', 'ta-IN', 'te-IN', 'gu-IN'].map((v) => (
                    <option key={v} value={v}>
                      {v}
                    </option>
                  ))}
                </SelectField>
                <SelectField
                  label="STT provider"
                  value={selected.sttProvider || 'sarvam'}
                  onChange={(v) => {
                    const models =
                      providerOpts?.stt_models?.[v] ||
                      (v === 'deepgram' ? [DEFAULT_STT_MODEL_DEEPGRAM, 'nova-3-general'] : [DEFAULT_STT_MODEL_SARVAM]);
                    updateSelected({ sttProvider: v, sttModel: models[0] });
                  }}
                >
                  {(sttProviderRows.length ? sttProviderRows : [{ id: 'sarvam', label: 'Sarvam' }]).map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.label || p.id}
                    </option>
                  ))}
                </SelectField>
                <SelectField label="STT model" value={selected.sttModel || DEFAULT_STT_MODEL_SARVAM} onChange={(v) => updateSelected({ sttModel: v })}>
                  {sttModelChoices.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </SelectField>
                <SelectField label="STT language" value={selected.sttLanguage || 'unknown'} onChange={(v) => updateSelected({ sttLanguage: v })}>
                  {(
                    providerOpts?.stt_providers?.find((p) => p.id === (selected.sttProvider || 'sarvam'))?.languages || [
                      'unknown',
                      'hi-IN',
                      'en-IN',
                      'ta-IN',
                    ]
                  ).map((lang) => (
                    <option key={lang} value={lang}>
                      {lang}
                    </option>
                  ))}
                </SelectField>
              </div>
              {!providerOpts && isApiConfigured && (
                <p className="mt-4 text-sm text-amber-700">Loading provider options…</p>
              )}
            </AppPanel>
          ) : activeTab === 'Engine' ? (
            <AppPanel title="Engine Settings" icon={Wrench}>
              <div className="grid gap-4 md:grid-cols-2">
                <SelectField
                  label="Language profile"
                  value={selected.defaultLanguage || 'multilingual'}
                  onChange={(v) => {
                    const preset = langProfiles.find((x) => x.id === v);
                    updateSelected({
                      defaultLanguage: v,
                      ...(preset?.tts_language && preset?.tts_voice
                        ? { ttsLanguage: preset.tts_language, ttsVoice: preset.tts_voice }
                        : { ttsLanguage: defaultTtsLanguageForProfile(v) }),
                    });
                  }}
                >
                  {(langProfiles.length
                    ? langProfiles
                    : [
                        { id: 'multilingual', label: 'Multilingual Auto' },
                        { id: 'english', label: 'English' },
                        { id: 'hindi', label: 'Hindi' },
                        { id: 'tamil', label: 'Tamil' },
                        { id: 'tamil_tanglish', label: 'Tamil / Tanglish' },
                      ]
                  ).map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.label || p.id}
                    </option>
                  ))}
                </SelectField>
                <SelectField
                  label="Vertical"
                  value={selected.vertical || ''}
                  onChange={(v) => updateSelected({ vertical: v })}
                >
                  <option value="">General</option>
                  <option value="tamil_real_estate">Tamil real estate</option>
                  <option value="real_estate">Real estate</option>
                  <option value="sales">Sales</option>
                  <option value="loan_collection">Loan collection</option>
                </SelectField>
                <EditableSettingField
                  label="STT endpointing delay (seconds)"
                  value={String(selected.sttMinEndpointingDelay ?? 0.05)}
                  onChange={(v) => {
                    const n = parseFloat(v);
                    updateSelected({ sttMinEndpointingDelay: Number.isFinite(n) ? Math.min(3, Math.max(0.02, n)) : 0.05 });
                  }}
                />
                <EditableSettingField
                  label="Max conversation turns"
                  value={String(selected.maxTurns ?? 14)}
                  onChange={(v) => {
                    const n = parseInt(v, 10);
                    updateSelected({ maxTurns: Number.isFinite(n) ? Math.min(60, Math.max(1, n)) : 14 });
                  }}
                />
                <EditableSettingField
                  label="Engine silence reference (seconds)"
                  value={String(selected.silenceTimeoutSeconds ?? 45)}
                  onChange={(v) => {
                    const n = parseInt(v, 10);
                    updateSelected({ silenceTimeoutSeconds: Number.isFinite(n) ? Math.min(600, Math.max(5, n)) : 45 });
                  }}
                />
                <div className="md:col-span-2">
                  <label className="block">
                    <span className="text-sm font-medium text-slate-600">Interruption / filler words (comma-separated)</span>
                    <input
                      value={selected.interruptionWords || ''}
                      onChange={(e) => updateSelected({ interruptionWords: e.target.value })}
                      className="mt-2 w-full rounded-md border border-slate-200 px-3 py-2 text-slate-900 outline-none focus:border-blue-400"
                      placeholder="okay, hmm, accha"
                    />
                  </label>
                </div>
                <SelectField
                  label="Response latency mode"
                  value={selected.responseLatencyMode || 'normal'}
                  onChange={(v) => updateSelected({ responseLatencyMode: v })}
                >
                  <option value="fast">Fast (shorter replies)</option>
                  <option value="normal">Normal</option>
                  <option value="quality">Quality (longer replies)</option>
                </SelectField>
              </div>
            </AppPanel>
          ) : activeTab === 'Call' ? (
            <AppPanel title="Call policy" icon={PhoneCall}>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="md:col-span-2">
                  <label className="block">
                    <span className="text-sm font-medium text-slate-600">Final / inactivity message (optional)</span>
                    <textarea
                      value={selected.finalCallMessage || ''}
                      onChange={(e) => updateSelected({ finalCallMessage: e.target.value })}
                      rows={3}
                      className="mt-2 w-full rounded-md border border-slate-200 px-3 py-2 text-slate-900 outline-none focus:border-blue-400"
                      placeholder="Played when the call ends due to inactivity (worker paraphrases)."
                    />
                  </label>
                </div>
                <label className="flex items-center gap-2 text-sm text-slate-800">
                  <input
                    type="checkbox"
                    checked={selected.silenceHangupEnabled ?? true}
                    onChange={(e) => updateSelected({ silenceHangupEnabled: e.target.checked })}
                  />
                  Silence hang-up (inactivity)
                </label>
                <EditableSettingField
                  label="Silence hang-up after (seconds)"
                  value={String(selected.silenceHangupSeconds ?? 45)}
                  onChange={(v) => {
                    const n = parseInt(v, 10);
                    updateSelected({ silenceHangupSeconds: Number.isFinite(n) ? Math.max(10, Math.min(600, n)) : 45 });
                  }}
                />
                <EditableSettingField
                  label="Max call duration (seconds, 0 = off)"
                  value={String(selected.totalCallTimeoutSeconds ?? 0)}
                  onChange={(v) => {
                    const n = parseInt(v, 10);
                    updateSelected({ totalCallTimeoutSeconds: Number.isFinite(n) ? Math.max(0, Math.min(7200, n)) : 0 });
                  }}
                />
                <label className="flex items-center gap-2 text-sm text-slate-800">
                  <input
                    type="checkbox"
                    checked={selected.warmTransferEnabled ?? true}
                    onChange={(e) => updateSelected({ warmTransferEnabled: e.target.checked })}
                  />
                  Warm transfer enabled (policy)
                </label>
                <EditableSettingField
                  label="Transfer destination (E.164)"
                  value={selected.transferDestinationE164 || ''}
                  onChange={(v) => updateSelected({ transferDestinationE164: v })}
                />
                <label className="flex items-center gap-2 text-sm text-slate-800">
                  <input
                    type="checkbox"
                    checked={selected.callRetryEnabled ?? true}
                    onChange={(e) => updateSelected({ callRetryEnabled: e.target.checked })}
                  />
                  Outbound retry enabled
                </label>
                <EditableSettingField
                  label="Max retries"
                  value={String(selected.callMaxRetries ?? 3)}
                  onChange={(v) => {
                    const n = parseInt(v, 10);
                    updateSelected({ callMaxRetries: Number.isFinite(n) ? Math.min(10, Math.max(0, n)) : 3 });
                  }}
                />
              </div>
            </AppPanel>
          ) : activeTab === 'Tools' ? (
            <AppPanel title="Tools" icon={Code}>
              <p className="mb-4 text-sm text-slate-600">
                Enable voice tools for the LiveKit worker. Custom function is UI-only (coming soon)—nothing is wired on the backend yet.
              </p>
              <ul className="space-y-3">
                {(
                  [
                    { id: 'check_availability', label: 'Calendar availability', desc: 'Check appointment slots' },
                    { id: 'save_booking_intent', label: 'Book appointment', desc: 'Save booking intent to calendar flow' },
                    { id: 'transfer_call', label: 'Transfer call', desc: 'Transfer to human (requires E.164 destination)' },
                    { id: 'custom_function', label: 'Custom function', desc: 'UI-only preview; no backend tool yet' },
                  ]
                ).map((row) => {
                  const tc = normalizeToolsConfig(selected.toolsConfig);
                  const cur = tc.find((t) => t.id === row.id);
                  const enabled = cur?.enabled ?? false;
                  const isCustom = row.id === 'custom_function';
                  return (
                    <li
                      key={row.id}
                      className={`flex flex-wrap items-center justify-between gap-3 rounded-md border px-4 py-3 ${
                        isCustom ? 'border-slate-100 bg-slate-50 text-slate-400' : 'border-slate-200'
                      }`}
                    >
                      <div>
                        <p className="font-semibold text-slate-900">{row.label}</p>
                        <p className="text-xs text-slate-500">{row.desc}</p>
                      </div>
                      {isCustom ? (
                        <div className="text-right text-xs text-slate-400">
                          <p className="font-semibold uppercase tracking-wide">Coming soon</p>
                          <p className="mt-1 font-normal normal-case text-slate-500">UI-only; no backend tool yet</p>
                        </div>
                      ) : (
                        <label className="flex items-center gap-2 text-sm">
                          <input
                            type="checkbox"
                            checked={enabled}
                            onChange={(e) => {
                              const next = tc.map((t) => (t.id === row.id ? { ...t, enabled: e.target.checked } : t));
                              updateSelected({ toolsConfig: next });
                            }}
                          />
                          Enabled
                        </label>
                      )}
                    </li>
                  );
                })}
              </ul>
            </AppPanel>
          ) : activeTab === 'Analytics' ? (
            <AppPanel title="Analytics" icon={ChartLineUp}>
              <p className="mb-4 text-sm text-slate-600">
                Stored on the agent version for dashboards and billing hooks. Does not change call audio by itself.
              </p>
              <label className="mb-4 flex items-center gap-2 text-sm text-slate-800">
                <input
                  type="checkbox"
                  checked={selected.analyticsTrackSummaries ?? true}
                  onChange={(e) => updateSelected({ analyticsTrackSummaries: e.target.checked })}
                />
                Track call summaries in logs
              </label>
              <label className="flex items-center gap-2 text-sm text-slate-800">
                <input
                  type="checkbox"
                  checked={selected.analyticsTrackProviderUsage ?? true}
                  onChange={(e) => updateSelected({ analyticsTrackProviderUsage: e.target.checked })}
                />
                Track provider usage events (cost estimates)
              </label>
            </AppPanel>
          ) : activeTab === 'Inbound' ? (
            <AppPanel title="Inbound routing" icon={PhoneIncoming}>
              <p className="mb-4 text-sm text-slate-600">
                Map this agent to an inbound number or SIP resource id stored on the agent record.
              </p>
              <label className="mb-4 flex items-center gap-2 text-sm text-slate-800">
                <input
                  type="checkbox"
                  checked={selected.inboundAssignEnabled ?? false}
                  onChange={(e) => updateSelected({ inboundAssignEnabled: e.target.checked })}
                />
                Assign inbound number / trunk id
              </label>
              <EditableSettingField
                label="Inbound number id / label"
                value={selected.inboundNumberId || ''}
                onChange={(v) => updateSelected({ inboundNumberId: v })}
              />
            </AppPanel>
          ) : (
            <AppPanel title={`${activeTab}`} icon={Info}>
              <p className="text-sm text-slate-600">
                {activeTab} settings use the tabs above (Agent through Inbound).
              </p>
            </AppPanel>
          )}
        </main>

        <aside className="flex min-h-0 flex-col space-y-5 overflow-y-auto border-slate-200 bg-white p-4 lg:border-l">
          <div className="rounded-lg border border-slate-200 p-4">
            <ShellButton primary className="mb-4 w-full" onClick={runPhoneCall} disabled={!selectedCanCall || callBusy !== null}>
              <PhoneIncoming size={20} /> {callBusy === 'phone' ? 'Calling...' : 'Get call from agent'}
            </ShellButton>
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
            <Link to="/logs" className="mb-5 flex min-h-10 w-full items-center justify-center gap-2 rounded-md border border-slate-200 bg-white px-4 text-base font-semibold text-slate-950 shadow-sm hover:bg-slate-50">
              See all call logs <ArrowSquareOut size={20} />
            </Link>
            <div className="grid grid-cols-[1fr_auto] gap-2">
              <ShellButton primary onClick={saveAgent} disabled={saving || publishing}>
                <FloppyDisk size={20} />{' '}
                {saving ? (
                  <span className="inline-flex items-center gap-2">
                    <Spinner className="h-4 w-4" label="Saving" />
                    Saving…
                  </span>
                ) : selected.dirty ? (
                  'Save draft'
                ) : (
                  'Save agent'
                )}
              </ShellButton>
              <ShellButton danger className="px-3"><Trash size={20} /></ShellButton>
            </div>
            <p className="mt-3 border-b border-slate-200 pb-5 text-sm italic text-slate-500">
              Calls require a published DB-backed UUID. Save and publish this agent before testing a call.
            </p>
            <ShellButton className="mt-6 w-full cursor-not-allowed bg-slate-100 text-slate-400" disabled type="button">
              <ChatCircleText size={20} /> Chat with agent (coming soon)
            </ShellButton>
            <p className="mt-3 text-center text-xs text-slate-500">Web chat is not connected yet. Use Test via browser or phone.</p>
            {callStatus && (
              <div className={`mt-4 rounded-md border px-3 py-2 text-sm ${
                callStatus.tone === 'success'
                  ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
                  : 'border-red-200 bg-red-50 text-red-700'
              }`}>
                <p>{callStatus.message}</p>
                {callStatus.tone === 'error' ? (
                  <div className="mt-2">
                    <ShellButton
                      className="w-full text-xs sm:w-auto"
                      onClick={() => {
                        void navigator.clipboard?.writeText(callStatus.message).catch(() => undefined);
                      }}
                    >
                      <Copy size={16} /> Copy error for support
                    </ShellButton>
                  </div>
                ) : null}
              </div>
            )}
            <div className="mt-6 rounded-lg border border-dashed border-slate-300 p-4 text-center">
              <ShellButton
                className="w-full border-dashed"
                onClick={runBrowserTest}
                disabled={callBusy !== null || Boolean(browserTestBlockReason)}
              >
                <Flask size={20} /> {callBusy === 'browser' ? 'Starting...' : 'Test via browser'} <span className="rounded bg-slate-100 px-2 py-1 text-xs text-slate-500">BETA</span>
              </ShellButton>
              {browserTestBlockReason && (
                <p className="mt-2 text-left text-xs text-amber-800">{browserTestBlockReason}</p>
              )}
              <ShellButton
                className="mt-3 w-full border-dashed border-amber-200 bg-amber-50/80 text-amber-950"
                onClick={runSipTestCall}
                disabled={!selectedCanCall || !sipTestReady || callBusy !== null}
              >
                <PhoneCall size={20} /> {callBusy === 'sip' ? 'Testing SIP...' : 'Test SIP Call'}
              </ShellButton>
              {!sipTestReady && isApiConfigured && (
                <p className="mt-2 text-xs text-slate-500">SIP test unlocks when LiveKit and SIP trunk health checks pass.</p>
              )}
              {!selectedCanCall && (
                <p className="mt-2 text-xs text-red-600">Save and publish this agent before running Phase 0 call proof.</p>
              )}
              <p className="mt-3 text-xs text-slate-500">For best experience, use "Get call from agent"</p>
            </div>
          </div>
        </aside>
      </div>
    </div>
    {aiEditOpen && (
      <div
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4"
        role="dialog"
        aria-modal="true"
        aria-labelledby="ai-edit-title"
      >
        <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-xl border border-slate-200 bg-white p-6 shadow-2xl">
          <h2 id="ai-edit-title" className="text-lg font-bold text-slate-950">
            AI prompt assistant
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            Uses your language profile and optional tone / business context. Results replace the prompt below — save the agent when you are happy with it.
          </p>
          <div className="mt-5 space-y-4">
            <SelectField label="Transformation" value={aiEditAction} onChange={(v) => setAiEditAction(v as PromptAssistAction)}>
              <option value="improve">Improve prompt</option>
              <option value="shorten">Shorten prompt</option>
              <option value="rewrite_professional">Rewrite professionally</option>
              <option value="optimize_sales">Optimize for sales</option>
              <option value="optimize_support">Optimize for support</option>
              <option value="optimize_real_estate">Optimize for real estate</option>
            </SelectField>
            <EditableSettingField
              label="Agent tone (optional)"
              value={selected.agentTone || ''}
              onChange={(v) => updateSelected({ agentTone: v })}
            />
            <EditableSettingField
              label="Business type (optional)"
              value={selected.businessType || ''}
              onChange={(v) => updateSelected({ businessType: v })}
            />
          </div>
          <p className="mt-4 text-xs text-slate-500">
            Current language profile:{' '}
            <span className="font-medium text-slate-700">
              {langProfiles.find((p) => p.id === (selected.defaultLanguage || 'multilingual'))?.label ||
                selected.defaultLanguage ||
                'multilingual'}
            </span>
            . Change it in the Audio tab (Language profile).
          </p>
          <div className="mt-6 flex flex-wrap justify-end gap-3 border-t border-slate-100 pt-5">
            <ShellButton
              onClick={() => {
                setAiEditOpen(false);
              }}
              disabled={aiEditLoading}
            >
              Cancel
            </ShellButton>
            <ShellButton primary onClick={runPromptAssist} disabled={aiEditLoading}>
              {aiEditLoading ? (
                <span className="inline-flex items-center gap-2">
                  <span
                    className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"
                    aria-hidden
                  />
                  Generating…
                </span>
              ) : (
                <>
                  <Sparkle size={18} weight="fill" /> Apply
                </>
              )}
            </ShellButton>
          </div>
        </div>
      </div>
    )}
    </>
  );
}

function SelectField({
  label,
  value,
  onChange,
  children,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-slate-600">{label}</span>
      <select
        className="mt-2 w-full rounded-md border border-slate-200 px-3 py-2 text-slate-900 outline-none focus:border-blue-400"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {children}
      </select>
    </label>
  );
}

function SettingField({ label, value }: { label: string; value: string }) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-slate-600">{label}</span>
      <input className="mt-2 w-full rounded-md border border-slate-200 px-3 py-2 text-slate-900 outline-none focus:border-blue-400" defaultValue={value} />
    </label>
  );
}

function EditableSettingField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-slate-600">{label}</span>
      <input
        className="mt-2 w-full rounded-md border border-slate-200 px-3 py-2 text-slate-900 outline-none focus:border-blue-400"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function Dashboard() {
  const [stats, setStats] = useState<AnalyticsSummary | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);
  const [health, setHealth] = useState<HealthPayload | null>(null);
  const [dashError, setDashError] = useState('');

  useEffect(() => {
    (async () => {
      setDashError('');
      try {
        setHealth(await api.health());
        setStats(await api.analytics());
      } catch (e: unknown) {
        setDashError(getErrorMessage(e, apiUnreachableMessage));
        setHealth(null);
        setStats(null);
      } finally {
        setStatsLoading(false);
      }
    })();
  }, []);

  return (
    <AppPage title="Dashboard" subtitle="Call performance and launch readiness for your voice agents.">
      {dashError ? (
        <div className="mb-6">
          <InlineBanner tone="error" title="We could not load dashboard data">
            {dashError}
          </InlineBanner>
        </div>
      ) : null}
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
    } catch (err: unknown) {
      setError(getErrorMessage(err, 'Call failed to dispatch.'));
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
      <ShellButton primary onClick={startCall} className="mt-5 w-full min-h-11 inline-flex justify-center gap-2">
        {loading ? (
          <>
            <Spinner className="h-5 w-5 text-white" label="Dispatching call" /> Dispatching…
          </>
        ) : (
          'Call Now'
        )}
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

function Crm() {
  const [rows, setRows] = useState<ContactRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError('');
      try {
        setRows(await api.contacts());
      } catch (err: unknown) {
        setError(getErrorMessage(err, 'Could not load CRM contacts.'));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <AppPage title="CRM Contacts" subtitle="Contacts discovered from call activity — a rollup of callers from your workspace.">
      {loading ? (
        <PageLoading message="Loading CRM…" />
      ) : error ? (
        <InlineBanner tone="error" title="CRM unavailable">
          {error}
        </InlineBanner>
      ) : rows.length === 0 ? (
        <EmptyWell
          title="No CRM contacts yet"
          description="After live calls capture caller details on the backend, contact cards will populate here automatically."
        >
          <Link to="/logs">
            <ShellButton>Open call history</ShellButton>
          </Link>
          <Link to="/agents">
            <ShellButton primary>Go to Agents</ShellButton>
          </Link>
        </EmptyWell>
      ) : (
        <div className="space-y-3">
          {rows.slice(0, 50).map((row, index) => (
            <div key={row.phone_e164 ?? row.phone ?? String(index)} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
              <div className="font-semibold text-slate-950">{row.full_name?.trim() || row.caller_name || 'Unknown'}</div>
              <div className="text-sm text-slate-600">{row.phone_e164?.trim() || row.phone || 'unknown'}</div>
              <div className="text-xs text-slate-500">Calls: {row.total_calls || 0}</div>
            </div>
          ))}
        </div>
      )}
    </AppPage>
  );
}

function Settings() {
  const [config, setConfig] = useState<Record<string, unknown>>({});
  const [message, setMessage] = useState('');

  useEffect(() => {
    (async () => setConfig(await api.config()))();
  }, []);

  const onSave = async () => {
    setMessage('');
    try {
      await api.saveConfig(config);
      setMessage('Config saved.');
    } catch (error: unknown) {
      setMessage(getErrorMessage(error, 'Failed to save config.'));
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

function ResourceList({ title, emptyText, icon: IconComponent }: { title: string; emptyText: string; icon: Icon }) {
  return (
    <AppPage title={title} subtitle="This module is ready for the next production workflow.">
      <div className="rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center shadow-sm">
        <IconComponent size={34} className="mx-auto mb-4 text-blue-600" />
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
  const [busy, setBusy] = useState<'checkout' | 'portal' | null>(null);
  const [message, setMessage] = useState('');

  useEffect(() => {
    (async () => setBilling(await api.billing()))();
  }, []);

  const startCheckout = async () => {
    setBusy('checkout');
    setMessage('');
    try {
      const session = await api.createCheckout();
      window.location.href = session.url;
    } catch (error: unknown) {
      setMessage(getErrorMessage(error, 'Unable to start checkout.'));
      setBusy(null);
    }
  };

  const openPortal = async () => {
    setBusy('portal');
    setMessage('');
    try {
      const session = await api.billingPortal();
      window.location.href = session.url;
    } catch (error: unknown) {
      setMessage(getErrorMessage(error, 'Unable to open billing portal.'));
      setBusy(null);
    }
  };

  return (
    <AppPage title="Billing" subtitle="Usage and trial billing summary.">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <div>
          <h2 className="font-bold text-slate-950">Subscription</h2>
          <p className="mt-1 text-sm text-slate-500">
            {billing?.stripe_configured ? 'Stripe checkout is connected.' : 'Stripe env is not configured yet.'}
          </p>
        </div>
        <div className="flex gap-2">
          <ShellButton primary onClick={startCheckout} disabled={busy !== null || billing?.stripe_configured === false}>
            <CreditCard size={18} /> {busy === 'checkout' ? 'Opening...' : 'Subscribe'}
          </ShellButton>
          <ShellButton onClick={openPortal} disabled={busy !== null || !billing?.stripe_customer_id}>
            <ArrowSquareOut size={18} /> {busy === 'portal' ? 'Opening...' : 'Manage'}
          </ShellButton>
        </div>
      </div>
      {message && <p className="mb-5 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">{message}</p>}
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
      {billing?.stripe_subscription_id && (
        <div className="mt-5 rounded-lg border border-slate-200 bg-white p-5 text-sm text-slate-600 shadow-sm">
          <p><span className="font-semibold text-slate-950">Subscription:</span> {billing.stripe_subscription_id}</p>
          {billing.current_period_end && (
            <p className="mt-2"><span className="font-semibold text-slate-950">Current period ends:</span> {new Date(billing.current_period_end * 1000).toLocaleDateString()}</p>
          )}
        </div>
      )}
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

function ProductionReadiness() {
  const [readiness, setReadiness] = useState<OpsReadiness | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        setReadiness(await api.opsReadiness());
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const items = readiness?.items || [];

  return (
    <AppPage title="Production" subtitle="Launch readiness across deploy, billing, security, calls, QA, and support.">
      {loading ? (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatCardSkeleton />
          <StatCardSkeleton />
          <StatCardSkeleton />
          <StatCardSkeleton />
        </div>
      ) : readiness ? (
        <>
          <div className="mb-5 grid gap-4 md:grid-cols-3">
            <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-sm text-slate-500">Readiness score</p>
              <p className="mt-2 text-4xl font-black text-slate-950">{readiness.score}%</p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-sm text-slate-500">Ready areas</p>
              <p className="mt-2 text-4xl font-black text-slate-950">{readiness.ready_count}/{readiness.total_count}</p>
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-sm text-slate-500">Status</p>
              <p className={`mt-2 text-2xl font-black ${readiness.status === 'ready' ? 'text-emerald-600' : 'text-amber-600'}`}>
                {readiness.status === 'ready' ? 'Ready' : 'Needs attention'}
              </p>
            </div>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            {items.map((item) => (
              <div key={item.key} className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
                <div className="mb-3 flex items-start justify-between gap-4">
                  <div>
                    <h2 className="font-bold text-slate-950">{item.label}</h2>
                    <p className="mt-1 text-sm leading-6 text-slate-600">{item.detail}</p>
                  </div>
                  <span className={`shrink-0 rounded-full px-3 py-1 text-xs font-bold ${item.ready ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>
                    {item.ready ? 'Ready' : 'Open'}
                  </span>
                </div>
                {item.action && <p className="text-sm leading-6 text-slate-500">{item.action}</p>}
              </div>
            ))}
          </div>
        </>
      ) : (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-6 text-amber-900">
          Production readiness is admin-only or the backend route is not deployed yet.
        </div>
      )}
    </AppPage>
  );
}

function Documentation() {
  const docs = [
    ['Deployment', 'Railway backend, Vercel frontend, environment variables, health checks'],
    ['Call QA', 'Browser test, SIP test call, outbound proof, inbound proof, log evidence'],
    ['Support', 'Customer issue intake, call room ID, phone number, timestamp, transcript, recording'],
    ['Security', 'Auth, workspace access, admin actions, secret rotation, incident response'],
  ];

  return (
    <AppPage title="Documentation" subtitle="Operator docs and support paths for production customers.">
      <div className="grid gap-4 lg:grid-cols-2">
        {docs.map(([title, copy]) => (
          <div key={title} className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-3 flex items-center gap-3">
              <BookOpen size={22} className="text-blue-600" />
              <h2 className="font-bold text-slate-950">{title}</h2>
            </div>
            <p className="text-sm leading-6 text-slate-600">{copy}</p>
          </div>
        ))}
      </div>
      <div className="mt-5 rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="font-bold text-slate-950">Support intake</h2>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {['Customer email', 'Phone number', 'Call room ID', 'Issue summary', 'Expected result', 'Actual result'].map((label) => (
            <label key={label} className="text-sm font-medium text-slate-600">
              {label}
              <input className="mt-2 w-full rounded-md border border-slate-200 px-3 py-2 outline-none focus:border-blue-400" readOnly />
            </label>
          ))}
        </div>
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

function AppPage({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <div className="min-h-full min-w-0 bg-slate-50 px-4 py-6 text-slate-950 sm:px-6 md:p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-black tracking-tight sm:text-3xl">{title}</h1>
        <p className="mt-2 text-sm text-slate-500">{subtitle}</p>
      </div>
      {children}
    </div>
  );
}

function SidebarLink({ to, icon: IconComponent, children }: { to: string, icon: Icon, children: React.ReactNode }) {
  const location = useLocation();
  const isActive =
    location.pathname === to ||
    (to === '/agents' && location.pathname === '/') ||
    (to === '/logs' && location.pathname.startsWith('/logs'));
  return (
    <Link
      to={to}
      className={`flex min-h-10 items-center gap-3 rounded-md px-4 text-sm font-semibold transition ${
        isActive ? 'bg-slate-100 text-slate-950' : 'text-slate-700 hover:bg-slate-50 hover:text-slate-950'
      }`}
    >
      <IconComponent size={21} weight={isActive ? 'fill' : 'regular'} className="text-slate-600" /> {children}
    </Link>
  );
}

function Layout({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const sessionNavigateTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [sessionNotice, setSessionNotice] = useState<string | null>(null);

  useEffect(() => {
    const handler = (ev: Event) => {
      const msg = (ev as CustomEvent<{ message?: string }>).detail?.message || sessionExpiredMessage;
      setSessionNotice(msg);
      if (sessionNavigateTimer.current) clearTimeout(sessionNavigateTimer.current);
      sessionNavigateTimer.current = setTimeout(() => {
        navigate('/login', { replace: true });
        setSessionNotice(null);
      }, 4200);
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, handler);
    return () => {
      window.removeEventListener(SESSION_EXPIRED_EVENT, handler);
      if (sessionNavigateTimer.current) clearTimeout(sessionNavigateTimer.current);
    };
  }, [navigate]);

  return (
    <div className="flex min-h-screen w-full min-w-0 flex-col bg-slate-50 text-slate-950 lg:h-screen lg:overflow-hidden lg:flex-row">
      <nav className="flex w-full shrink-0 flex-col overflow-y-auto border-b border-slate-200 bg-white lg:h-full lg:w-[210px] lg:border-r lg:border-b-0">
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
            <SidebarLink to="/production" icon={ShieldCheck}>Production</SidebarLink>
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
      <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-auto">
        {sessionNotice ? (
          <div className="sticky top-0 z-30 border-b border-amber-200 bg-amber-50 px-4 py-3 sm:px-6">
            <InlineBanner
              tone="warning"
              title="Session ended"
              onDismiss={() => {
                if (sessionNavigateTimer.current) clearTimeout(sessionNavigateTimer.current);
                navigate('/login', { replace: true });
                setSessionNotice(null);
              }}
            >
              {sessionNotice}
            </InlineBanner>
          </div>
        ) : null}
        {import.meta.env.PROD && !isSupabaseConfigured ? (
          <div className="border-b border-amber-100 bg-amber-50/90 px-4 py-3 sm:px-6">
            <InlineBanner tone="warning" title="Sign-in misconfigured">
              {missingSupabaseEnvMessage}
            </InlineBanner>
          </div>
        ) : null}
        {!isApiConfigured ? (
          <div className="border-b border-amber-200 bg-amber-50 px-4 py-3 text-sm font-medium text-amber-900 sm:px-6">{apiConnectionMessage}</div>
        ) : null}
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
    return (
      <div className="min-h-screen min-w-0 bg-slate-50">
        <PageLoading message="Checking your session…" />
      </div>
    );
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
        <Route path="/config-check" element={<ConfigCheck />} />
        <Route
          path="*"
          element={
            <ProtectedRoute>
              <Layout>
                <Routes>
                  <Route path="/dashboard" element={<Dashboard />} />
                  <Route path="/agents" element={<Agents />} />
                  <Route path="/terminal" element={<TerminalPage />} />
                  <Route path="/logs" element={<CallLogsPage />} />
                  <Route path="/logs/:callId" element={<CallLogDetail />} />
                  <Route path="/calls" element={<Navigate to="/logs" replace />} />
                  <Route path="/numbers" element={<ResourceList title="My Numbers" icon={Hash} emptyText="No phone numbers connected yet." />} />
                  <Route path="/sip-trunks" element={<ResourceList title="SIP Trunks" icon={PhoneCall} emptyText="No SIP trunks connected yet." />} />
                  <Route path="/knowledge-base" element={<ResourceList title="Knowledge Base" icon={Database} emptyText="No knowledge base sources uploaded yet." />} />
                  <Route path="/batches" element={<ResourceList title="Batches" icon={Stack} emptyText="No batches created yet." />} />
                  <Route path="/developers" element={<ResourceList title="Developers" icon={Code} emptyText="No developer keys or webhooks configured yet." />} />
                  <Route path="/providers" element={<ResourceList title="Providers" icon={PlugsConnected} emptyText="No voice or telephony providers configured yet." />} />
                  <Route path="/workflows" element={<ResourceList title="Workflows" icon={GitBranch} emptyText="No workflows created yet." />} />
                  <Route path="/campaigns" element={<Campaigns />} />
                  <Route path="/production" element={<ProductionReadiness />} />
                  <Route path="/documentation" element={<Documentation />} />
                  <Route path="/analytics" element={<Analytics />} />
                  <Route path="/crm" element={<Crm />} />
                  <Route path="/leads" element={<Navigate to="/crm" replace />} />
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
