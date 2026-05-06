/** Small shared UI primitives for loading / empty / errors (no new dependencies). */

import type { ReactNode } from "react";

export function Spinner({ className = "h-5 w-5", label }: { className?: string; label?: string }) {
  return (
    <span
      className={`inline-block animate-spin rounded-full border-2 border-current border-t-transparent ${className}`}
      role={label ? "status" : undefined}
      aria-label={label || "Loading"}
    />
  );
}

export function PageLoading({ message = "Loading…" }: { message?: string }) {
  return (
    <div className="flex min-h-[40vh] flex-col items-center justify-center gap-3 bg-slate-50 p-8 text-slate-600">
      <Spinner className="h-8 w-8 text-blue-600" label={message} />
      <p className="text-sm font-medium">{message}</p>
    </div>
  );
}

export function EmptyWell({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children?: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-6 py-10 text-center shadow-sm">
      <h3 className="text-lg font-bold text-slate-950">{title}</h3>
      <p className="mx-auto mt-2 max-w-md text-sm text-slate-600">{description}</p>
      {children ? <div className="mt-6 flex flex-wrap justify-center gap-3">{children}</div> : null}
    </div>
  );
}

export function InlineBanner({
  tone,
  title,
  children,
  onDismiss,
}: {
  tone: "error" | "warning" | "info" | "success";
  title?: string;
  children: React.ReactNode;
  onDismiss?: () => void;
}) {
  const toneClass =
    tone === "error"
      ? "border-red-200 bg-red-50 text-red-900"
      : tone === "warning"
        ? "border-amber-200 bg-amber-50 text-amber-950"
        : tone === "success"
          ? "border-emerald-200 bg-emerald-50 text-emerald-900"
          : "border-blue-200 bg-blue-50 text-blue-900";
  return (
    <div className={`rounded-lg border px-4 py-3 text-sm ${toneClass}`} role="status">
      <div className="flex items-start justify-between gap-3">
        <div>
          {title ? <p className="font-semibold">{title}</p> : null}
          <div className={title ? "mt-1" : ""}>{children}</div>
        </div>
        {onDismiss ? (
          <button
            type="button"
            onClick={onDismiss}
            className="shrink-0 rounded px-2 py-0.5 text-xs font-semibold opacity-80 hover:opacity-100"
          >
            Dismiss
          </button>
        ) : null}
      </div>
    </div>
  );
}
