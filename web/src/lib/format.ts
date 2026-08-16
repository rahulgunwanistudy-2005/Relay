import type { LifecycleKind, Member, Provenance } from "./types";

// Lifecycle vocabulary — the hidden work behind one sentence.
export const LIFECYCLE: Record<
  LifecycleKind,
  { label: string; gloss: string }
> = {
  anticipate: { label: "Anticipate", gloss: "Noticing it before it's urgent" },
  options: { label: "Weigh options", gloss: "Comparing the ways to do it" },
  decide: { label: "Decide", gloss: "Committing to one path" },
  prepare: { label: "Prepare", gloss: "Getting what's needed ready" },
  execute: { label: "Do it", gloss: "The visible task itself" },
  verify: { label: "Verify", gloss: "Checking it actually landed" },
  follow_up: { label: "Follow up", gloss: "Closing the loop afterward" },
  recur: { label: "Recur", gloss: "It comes back around" },
};

export const LIFECYCLE_ORDER: LifecycleKind[] = [
  "anticipate",
  "options",
  "decide",
  "prepare",
  "execute",
  "verify",
  "follow_up",
  "recur",
];

export const PROVENANCE_META: Record<
  Provenance,
  { label: string; short: string }
> = {
  user_explicit: { label: "You said this", short: "You" },
  ai_inferred: { label: "Suggested", short: "Suggested" },
  deterministic: { label: "From your words", short: "Parsed" },
};

const DAY = 86400000;

export function relativeTime(iso: string | null, now = Date.now()): string {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  const diff = t - now;
  const abs = Math.abs(diff);
  const fut = diff >= 0;
  if (abs < 60_000) return "now";
  if (abs < 3_600_000) {
    const m = Math.round(abs / 60_000);
    return fut ? `in ${m} min` : `${m} min ago`;
  }
  if (abs < DAY) {
    const h = Math.round(abs / 3_600_000);
    return fut ? `in ${h}h` : `${h}h ago`;
  }
  const d = Math.round(abs / DAY);
  if (d < 30) return fut ? `in ${d} day${d > 1 ? "s" : ""}` : `${d} day${d > 1 ? "s" : ""} ago`;
  const mo = Math.round(d / 30);
  return fut ? `in ${mo} month${mo > 1 ? "s" : ""}` : `${mo} month${mo > 1 ? "s" : ""} ago`;
}

export function calendarDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function clockTime(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });
}

export function firstName(name: string): string {
  return name.trim().split(/\s+/)[0] || name;
}

export function memberName(members: Member[] | undefined, membershipId: string | null): string {
  if (!membershipId) return "Unassigned";
  const m = members?.find((x) => x.id === membershipId);
  return m ? m.display_name : "a member";
}

export function memberFirst(members: Member[] | undefined, membershipId: string | null): string {
  return firstName(memberName(members, membershipId));
}

export function reminderLabel(kind: string): string {
  switch (kind) {
    case "step_due":
      return "A step comes due";
    case "cycle_due":
      return "The whole thing is due";
    case "overdue":
      return "It's overdue";
    case "escalation":
      return "Escalation";
    default:
      return kind;
  }
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return (parts[0]?.[0] ?? "?").toUpperCase() + (parts[1]?.[0]?.toUpperCase() ?? "");
}
