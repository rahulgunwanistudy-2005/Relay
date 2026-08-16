import type { ButtonHTMLAttributes, ReactNode } from "react";
import "./ui.css";

type Variant = "primary" | "ghost" | "quiet" | "danger";

interface BtnProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  pending?: boolean;
  confirmed?: boolean;
}

export function Button({
  variant = "primary",
  pending = false,
  confirmed = false,
  children,
  disabled,
  className = "",
  ...rest
}: BtnProps) {
  return (
    <button
      className={`btn btn--${variant} ${pending ? "btn--pending" : ""} ${
        confirmed ? "btn--confirmed" : ""
      } ${className}`}
      disabled={disabled || pending}
      aria-busy={pending}
      {...rest}
    >
      <span className="btn__label">{children}</span>
      {pending && <span className="btn__spinner" aria-hidden />}
    </button>
  );
}

export function Field({
  label,
  hint,
  children,
  id,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
  id?: string;
}) {
  return (
    <label className="field" htmlFor={id}>
      <span className="field__label label">{label}</span>
      {children}
      {hint && <span className="field__hint">{hint}</span>}
    </label>
  );
}

export function Banner({ tone, children }: { tone: "error" | "info"; children: ReactNode }) {
  return (
    <div className={`banner banner--${tone}`} role={tone === "error" ? "alert" : "status"}>
      {children}
    </div>
  );
}

export function Pill({ children, tone }: { children: ReactNode; tone?: string }) {
  return <span className={`pill ${tone ? `pill--${tone}` : ""}`}>{children}</span>;
}

export function Avatar({ name, muted }: { name: string; muted?: boolean }) {
  const parts = name.trim().split(/\s+/);
  const init = (parts[0]?.[0] ?? "?").toUpperCase() + (parts[1]?.[0]?.toUpperCase() ?? "");
  return (
    <span className={`avatar ${muted ? "avatar--muted" : ""}`} aria-hidden>
      {init}
    </span>
  );
}
