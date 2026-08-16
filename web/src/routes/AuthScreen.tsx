import { useState } from "react";
import "./auth.css";
import { api } from "@/lib/api";
import { useSession } from "@/auth/session";
import { Banner, Button, Field } from "@/components/ui";

export function AuthScreen() {
  const { signIn } = useSession();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      const res =
        mode === "register"
          ? await api.register(email.trim(), password, name.trim())
          : await api.login(email.trim(), password);
      await signIn(res.access_token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="auth">
      <div className="auth__stage">
        <div className="auth__pitch">
          <p className="label">A responsibility ledger</p>
          <h1 className="auth__headline display">
            The task can move.
            <br />
            The <span className="auth__accent">remembering</span> usually doesn't.
          </h1>
          <p className="auth__sub">
            Relay hands over the whole shape of a responsibility — the noticing, deciding,
            preparing and following up — so the person who used to carry it can genuinely
            stop.
          </p>
          <ThreadSketch />
        </div>

        <form className="auth__form" onSubmit={submit}>
          <div className="auth__tabs" role="tablist" aria-label="Sign in or create account">
            <button
              type="button"
              role="tab"
              aria-selected={mode === "login"}
              className={mode === "login" ? "is-on" : ""}
              onClick={() => setMode("login")}
            >
              Sign in
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === "register"}
              className={mode === "register" ? "is-on" : ""}
              onClick={() => setMode("register")}
            >
              Create account
            </button>
          </div>

          {mode === "register" && (
            <Field label="Your name" id="name">
              <input
                id="name"
                className="input"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Alice Rivera"
                required
                autoComplete="name"
              />
            </Field>
          )}
          <Field label="Email" id="email">
            <input
              id="email"
              className="input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@home.example"
              required
              autoComplete="email"
            />
          </Field>
          <Field label="Password" id="password">
            <input
              id="password"
              className="input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 8 characters"
              required
              minLength={8}
              autoComplete={mode === "register" ? "new-password" : "current-password"}
            />
          </Field>

          {error && <Banner tone="error">{error}</Banner>}

          <Button type="submit" pending={pending}>
            {mode === "register" ? "Create account" : "Sign in"}
          </Button>
          <p className="auth__fine">
            Real accounts, real Postgres. Two people can sign in and hand a responsibility
            between them.
          </p>
        </form>
      </div>
    </div>
  );
}

function ThreadSketch() {
  return (
    <svg className="auth__thread" viewBox="0 0 260 120" fill="none" aria-hidden>
      <path
        d="M20 22C20 22 96 18 96 60S20 98 20 98"
        stroke="var(--hairline-strong)"
        strokeWidth="1.5"
        strokeDasharray="3 5"
      />
      <path
        d="M150 22C150 22 226 18 240 60"
        stroke="var(--thread)"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <circle cx="20" cy="22" r="3.4" fill="var(--ink-1)" />
      <circle cx="20" cy="60" r="2.6" fill="var(--hairline-strong)" />
      <circle cx="20" cy="98" r="2.6" fill="var(--hairline-strong)" />
      <circle cx="150" cy="22" r="3.4" fill="var(--thread)" />
      <circle cx="240" cy="60" r="2.6" fill="var(--thread-soft)" />
      <text x="14" y="12" className="auth__thread-label">
        before
      </text>
      <text x="144" y="12" className="auth__thread-label">
        after
      </text>
    </svg>
  );
}
