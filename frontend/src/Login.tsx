import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  appMisconfiguredUserMessage,
  envIssueMessages,
  isApiConfigured,
  isPublicEnvValid,
} from "./lib/env";
import { getAuthRedirectUrl, isSupabaseConfigured, supabase } from "./lib/supabase";
import { Spinner } from "./components/UiFeedback";

function getErrorMessage(data: unknown, fallback: string) {
  if (data instanceof Error) return data.message;
  if (!data || typeof data !== "object") return fallback;
  const payload = data as { detail?: string | { message?: string }; message?: string };
  if (typeof payload.detail === "string") return payload.detail;
  if (typeof payload.detail?.message === "string") return payload.detail.message;
  if (typeof payload.message === "string") return payload.message;
  return fallback;
}

export default function Login() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [messageTone, setMessageTone] = useState<"error" | "success" | "info">("error");
  const [videoFailed, setVideoFailed] = useState(false);

  useEffect(() => {
    if (!isSupabaseConfigured) return;
    supabase.auth.getSession().then(({ data }) => {
      if (data.session?.access_token) navigate("/agents", { replace: true });
    });
  }, [navigate]);

  const resetMode = (nextMode: "login" | "signup") => {
    setMode(nextMode);
    setMessage("");
  };

  const ensureSessionThenNavigate = async () => {
    const { data } = await supabase.auth.getSession();
    if (!data.session?.access_token) {
      throw new Error("Authentication succeeded, but no session was returned.");
    }
    navigate("/agents");
  };

  const submit = async () => {
    if (!isPublicEnvValid || !isSupabaseConfigured || !isApiConfigured) {
      setMessage(appMisconfiguredUserMessage);
      setMessageTone("error");
      return;
    }
    setLoading(true);
    setMessage("");
    try {
      if (mode === "signup") {
        const { data, error } = await supabase.auth.signUp({
          email,
          password,
          options: { emailRedirectTo: getAuthRedirectUrl("/agents") },
        });
        if (error) throw new Error(getErrorMessage(error, "Signup failed"));
        if (data.session?.access_token) {
          navigate("/agents");
          return;
        }
        setMessage("Signup successful. Check your email/Gmail to verify your account.");
        setMessageTone("success");
        return;
      }

      const { error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) throw new Error(getErrorMessage(error, "Authentication failed"));
      await ensureSessionThenNavigate();
    } catch (e: unknown) {
      setMessage(getErrorMessage(e, "Authentication failed"));
      setMessageTone("error");
    } finally {
      setLoading(false);
    }
  };

  const loginWithGoogle = async () => {
    if (!isPublicEnvValid || !isSupabaseConfigured || !isApiConfigured) {
      setMessage(appMisconfiguredUserMessage);
      setMessageTone("error");
      return;
    }
    setLoading(true);
    setMessage("");
    try {
      const { error } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: { redirectTo: getAuthRedirectUrl("/agents") },
      });
      if (error) throw new Error(getErrorMessage(error, "Google login failed"));
    } catch (e: unknown) {
      setMessage(getErrorMessage(e, "Google login failed"));
      setMessageTone("error");
      setLoading(false);
    }
  };

  const modeLabel = mode === "login" ? "Sign in to continue" : "Create your account";
  const submitLabel = mode === "login" ? "Login" : "Sign up";
  const submitAriaLabel = mode === "login" ? "Submit login" : "Submit signup";
  const authActionsDisabled = !isPublicEnvValid || !isSupabaseConfigured || !isApiConfigured || loading;

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-gradient-to-br from-gray-950 via-slate-900 to-black px-4 py-8 text-gray-100 sm:p-6">
      {!videoFailed && (
        <video
          src="/bgaisound.mp4"
          aria-hidden="true"
          autoPlay
          muted
          loop
          playsInline
          preload="auto"
          onError={() => setVideoFailed(true)}
          className="absolute inset-0 h-full w-full object-cover opacity-75"
        />
      )}
      <div className="pointer-events-none absolute inset-0 bg-black/60" />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_80%_50%_at_50%_-20%,rgba(99,102,241,0.22),transparent)]" />
      <div className="relative z-10 w-full max-w-md rounded-2xl border border-gray-700/80 bg-gray-900/90 p-6 shadow-2xl shadow-black/40 ring-1 ring-white/5 backdrop-blur-sm sm:p-8">
        <h1 className="text-2xl font-bold tracking-tight bg-gradient-to-r from-indigo-400 to-cyan-400 bg-clip-text text-transparent mb-2">
          Jettone
        </h1>
        <p className="text-gray-400 text-sm mb-6">
          {modeLabel}
        </p>
        {!isPublicEnvValid && (
          <div className="mb-4 rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-100">
            <p>{appMisconfiguredUserMessage}</p>
            {envIssueMessages.length > 0 ? (
              <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-red-200/90">
                {envIssueMessages.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            ) : null}
          </div>
        )}
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-2 rounded-xl border border-gray-700 bg-gray-950 p-1">
            {[
              ["login", "Login"],
              ["signup", "Sign up"],
            ].map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => resetMode(value as "login" | "signup")}
                className={`rounded-lg px-3 py-2 text-sm font-semibold transition-colors ${
                  mode === value ? "bg-indigo-600 text-white" : "text-gray-400 hover:bg-gray-800 hover:text-white"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <input
            type="email"
            placeholder="Email"
            autoComplete="email"
            className="w-full rounded-lg bg-gray-950 border border-gray-700 px-4 py-3 text-gray-100 placeholder:text-gray-500 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/30 transition-shadow"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <input
            type="password"
            placeholder="Password"
            autoComplete={mode === "signup" ? "new-password" : "current-password"}
            className="w-full rounded-lg bg-gray-950 border border-gray-700 px-4 py-3 text-gray-100 placeholder:text-gray-500 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/30 transition-shadow"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {message && (
            <p className={`text-sm ${messageTone === "success" ? "text-green-400" : messageTone === "info" ? "text-yellow-300" : "text-red-400"}`}>
              {message}
            </p>
          )}
          <button
            type="button"
            onClick={submit}
            disabled={authActionsDisabled}
            aria-label={submitAriaLabel}
            aria-busy={loading}
            className="inline-flex w-full items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 disabled:pointer-events-none py-3 rounded-lg font-semibold shadow-lg shadow-indigo-900/30 transition-colors"
          >
            {loading ? (
              <>
                <Spinner className="h-4 w-4 text-white" label="Signing in" />
                <span>Please wait…</span>
              </>
            ) : (
              submitLabel
            )}
          </button>
          <button
            type="button"
            onClick={loginWithGoogle}
            disabled={authActionsDisabled}
            className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-gray-700 bg-gray-950 py-3 font-semibold text-gray-100 transition-colors hover:border-gray-500 hover:bg-gray-800 disabled:pointer-events-none disabled:opacity-60"
          >
            {loading ? (
              <>
                <Spinner className="h-4 w-4" label="Continuing with Google" />
                <span>Please wait…</span>
              </>
            ) : (
              "Continue with Google"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
