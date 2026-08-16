import { NavLink, useNavigate } from "react-router-dom";
import type { ReactNode } from "react";
import "./shell.css";
import { useSession } from "@/auth/session";
import { useHouseholds, useIncomingHandoffs } from "@/lib/queries";
import { firstName } from "@/lib/format";

export function Shell({
  children,
  onJudge,
  dimmed,
}: {
  children: ReactNode;
  onJudge: () => void;
  dimmed?: boolean;
}) {
  const { user, householdId, setHouseholdId, signOut } = useSession();
  const households = useHouseholds(!!user);
  const inbox = useIncomingHandoffs();
  const navigate = useNavigate();
  const pending = inbox.data?.length ?? 0;
  const active = households.data?.find((h) => h.id === householdId);

  return (
    <div className={`shell ${dimmed ? "shell--dimmed" : ""}`}>
      <header className="topbar">
        <div className="topbar__left">
          <button className="brand" onClick={() => navigate("/")} aria-label="Relay home">
            <span className="brand__mark" aria-hidden>
              <ThreadGlyph />
            </span>
            <span className="brand__word">Relay</span>
          </button>
          {active && households.data && households.data.length > 1 ? (
            <select
              className="hh-select"
              value={householdId ?? ""}
              onChange={(e) => setHouseholdId(e.target.value)}
              aria-label="Active household"
            >
              {households.data.map((h) => (
                <option key={h.id} value={h.id}>
                  {h.name}
                </option>
              ))}
            </select>
          ) : active ? (
            <span className="hh-name">{active.name}</span>
          ) : null}
        </div>

        <nav className="topnav" aria-label="Primary">
          <NavLink to="/" end className="topnav__link">
            My load
          </NavLink>
          <NavLink to="/inbox" className="topnav__link">
            Incoming
            {pending > 0 && <span className="topnav__badge">{pending}</span>}
          </NavLink>
          <NavLink to="/household" className="topnav__link">
            Household
          </NavLink>
        </nav>

        <div className="topbar__right">
          <button className="judge-btn" onClick={onJudge} title="Play the 40-second demo (J)">
            Judge mode
          </button>
          {user && (
            <div className="account">
              <span className="account__name">{firstName(user.display_name)}</span>
              <button className="account__out" onClick={signOut}>
                Sign out
              </button>
            </div>
          )}
        </div>
      </header>
      <main className="canvas">{children}</main>
    </div>
  );
}

function ThreadGlyph() {
  return (
    <svg width="18" height="22" viewBox="0 0 18 22" fill="none">
      <path
        d="M9 1.5C9 5 4 6 4 10.5S14 16 14 20.5"
        stroke="var(--thread)"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      <circle cx="9" cy="1.8" r="1.8" fill="var(--ink-0)" />
      <circle cx="14" cy="20.4" r="1.8" fill="var(--thread)" />
    </svg>
  );
}
