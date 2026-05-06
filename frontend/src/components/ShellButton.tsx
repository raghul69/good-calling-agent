export function ShellButton({
  children,
  primary = false,
  danger = false,
  className = '',
  onClick,
  disabled = false,
}: {
  children: React.ReactNode;
  primary?: boolean;
  danger?: boolean;
  className?: string;
  onClick?: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex min-h-10 items-center justify-center gap-2 rounded-md border px-4 text-sm font-semibold shadow-sm transition ${
        primary
          ? 'border-blue-600 bg-blue-600 text-white hover:bg-blue-700'
          : danger
            ? 'border-slate-200 bg-white text-slate-900 hover:border-red-200 hover:bg-red-50 hover:text-red-700'
            : 'border-slate-200 bg-white text-slate-950 hover:bg-slate-50'
      } disabled:cursor-not-allowed disabled:opacity-50 ${className}`}
    >
      {children}
    </button>
  );
}
