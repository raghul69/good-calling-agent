import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { setAccessToken } from "./auth";

function getErrorMessage(data: any, fallback: string) {
  if (typeof data?.detail === "string") return data.detail;
  if (typeof data?.detail?.message === "string") return data.detail.message;
  if (typeof data?.message === "string") return data.message;
  return fallback;
}

export default function Login() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<"login" | "signup" | "otp">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [otp, setOtp] = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [messageTone, setMessageTone] = useState<"error" | "success" | "info">("error");

  const submit = async () => {
    setLoading(true);
    setMessage("");
    try {
      if (mode === "otp") {
        const endpoint = otpSent ? "/api/auth/otp/verify" : "/api/auth/otp/send";
        const res = await fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(otpSent ? { email, token: otp } : { email }),
        });
        const data = await res.json();
        if (!res.ok) {
          const apiMessage = getErrorMessage(data, "OTP failed");
          const waitMatch = apiMessage.match(/after\s+(\d+)\s+seconds/i);
          if (waitMatch) {
            setMessage(`Please wait ${waitMatch[1]} seconds before requesting another OTP.`);
            setMessageTone("info");
            return;
          }
          throw new Error(apiMessage);
        }
        if (!otpSent) {
          setOtpSent(true);
          setMessage("OTP sent. Check your email.");
          setMessageTone("success");
          return;
        }
        if (!data?.access_token) {
          throw new Error("No access token returned by server");
        }
        setAccessToken(data.access_token);
        navigate("/");
        return;
      }

      const endpoint = mode === "login" ? "/api/auth/login" : "/api/auth/signup";
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(getErrorMessage(data, "Authentication failed"));
      }

      if (mode === "signup") {
        setMode("login");
        setMessage("Signup successful. Please log in.");
        setMessageTone("success");
        return;
      }

      if (!data?.access_token) {
        throw new Error("No access token returned by server");
      }
      setAccessToken(data.access_token);
      navigate("/");
    } catch (e: any) {
      setMessage(e.message || "Authentication failed");
      setMessageTone("error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex items-center justify-center p-6 relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_80%_50%_at_50%_-20%,rgba(99,102,241,0.22),transparent)]" />
      <div className="relative w-full max-w-md rounded-2xl border border-gray-700/80 bg-gray-900/90 p-8 shadow-2xl shadow-black/40 ring-1 ring-white/5 backdrop-blur-sm">
        <h1 className="text-2xl font-bold tracking-tight bg-gradient-to-r from-indigo-400 to-cyan-400 bg-clip-text text-transparent mb-2">
          RapidX Voice OS
        </h1>
        <p className="text-gray-400 text-sm mb-6">
          {mode === "login" ? "Sign in to continue" : mode === "signup" ? "Create your account" : "Login with email OTP"}
        </p>
        <div className="space-y-4">
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
            className="w-full rounded-lg bg-gray-950 border border-gray-700 px-4 py-3 text-gray-100 placeholder:text-gray-500 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/30 transition-shadow disabled:opacity-50"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            hidden={mode === "otp"}
            disabled={mode === "otp"}
          />
          {mode === "otp" && otpSent && (
            <input
              type="text"
              inputMode="numeric"
              placeholder="Email OTP"
              autoComplete="one-time-code"
              className="w-full rounded-lg bg-gray-950 border border-gray-700 px-4 py-3 text-gray-100 placeholder:text-gray-500 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/30 transition-shadow"
              value={otp}
              onChange={(e) => setOtp(e.target.value)}
            />
          )}
          {message && (
            <p className={`text-sm ${messageTone === "success" ? "text-green-400" : messageTone === "info" ? "text-yellow-300" : "text-red-400"}`}>
              {message}
            </p>
          )}
          <button
            type="button"
            onClick={submit}
            disabled={loading}
            aria-busy={loading}
            className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-60 disabled:pointer-events-none py-3 rounded-lg font-semibold shadow-lg shadow-indigo-900/30 transition-colors"
          >
            {loading ? "Please wait..." : mode === "otp" ? (otpSent ? "Verify OTP" : "Send OTP") : mode === "login" ? "Login" : "Sign up"}
          </button>
          <button
            onClick={() => {
              setMode(mode === "login" ? "signup" : "login");
              setOtpSent(false);
              setOtp("");
              setMessage("");
            }}
            className="w-full text-sm text-gray-300 hover:text-white"
          >
            {mode === "login" ? "Need an account? Sign up" : "Already have an account? Login"}
          </button>
          <button
            onClick={() => {
              setMode(mode === "otp" ? "login" : "otp");
              setOtpSent(false);
              setOtp("");
              setMessage("");
            }}
            className="w-full text-sm text-gray-300 hover:text-white"
          >
            {mode === "otp" ? "Use password login" : "Login with email OTP"}
          </button>
        </div>
      </div>
    </div>
  );
}
