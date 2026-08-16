import { useMemo } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import "./myload.css";
import { useSession } from "@/auth/session";
import {
  useGhostQueue,
  useIncomingHandoffs,
  useMembers,
  useResponsibilities,
} from "@/lib/queries";
import { calendarDate, firstName, relativeTime, reminderLabel } from "@/lib/format";
import type { GhostQueueItem, ResponsibilitySummary } from "@/lib/types";
import { Pill } from "@/components/ui";

const DAY = 86400000;

export function MyLoad({ onJudge }: { onJudge: () => void }) {
  const { user, householdId } = useSession();
  const members = useMembers(householdId);
  const responsibilities = useResponsibilities(householdId);
  const queue = useGhostQueue();
  const inbox = useIncomingHandoffs();

  const myMembershipId = useMemo(
    () => members.data?.find((m) => m.user_id === user?.id)?.id ?? null,
    [members.data, user?.id],
  );

  const titleById = useMemo(() => {
    const map = new Map<string, string>();
    responsibilities.data?.forEach((r) => map.set(r.id, r.title));
    return map;
  }, [responsibilities.data]);

  const mine = useMemo(
    () =>
      responsibilities.data?.filter(
        (r) => r.current_owner_membership_id === myMembershipId && r.status !== "completed",
      ) ?? [],
    [responsibilities.data, myMembershipId],
  );

  const buckets = useMemo(() => bucketQueue(queue.data ?? []), [queue.data]);
  const loading = members.isLoading || responsibilities.isLoading || queue.isLoading;

  const totalQueue = queue.data?.length ?? 0;
  const nothing = !loading && mine.length === 0 && totalQueue === 0;

  return (
    <div className="load">
      <header className="load__head">
        <div>
          <p className="label">{greeting()}, {firstName(user?.display_name ?? "")}</p>
          <h1 className="load__title display">What are you still carrying?</h1>
        </div>
        <Link to="/new" className="load__capture">
          <span className="load__capture-plus" aria-hidden>
            +
          </span>
          Name a responsibility
        </Link>
      </header>

      {inbox.data && inbox.data.length > 0 && (
        <Link to="/inbox" className="load__inbox">
          <span className="load__inbox-dot" aria-hidden />
          <span>
            {inbox.data.length === 1
              ? `${firstName(inbox.data[0].proposer_display_name)} wants to hand you `
              : `${inbox.data.length} responsibilities are waiting for you — starting with `}
            <strong>{inbox.data[0].responsibility_title}</strong>
          </span>
          <span className="load__inbox-go">Review →</span>
        </Link>
      )}

      {nothing ? (
        <Quiet />
      ) : (
        <div className="load__grid">
          <section className="load__col" aria-labelledby="queue-h">
            <h2 id="queue-h" className="load__colhead label">
              Coming due for you
            </h2>
            {totalQueue === 0 && !loading && (
              <p className="load__calm">
                Nothing is scheduled for you right now. That's the point.
              </p>
            )}
            {(["now", "soon", "later"] as const).map((key) =>
              buckets[key].length > 0 ? (
                <div className="qbucket" key={key}>
                  <p className="qbucket__label label">{key}</p>
                  <ul className="qlist">
                    {buckets[key].map((item) => (
                      <QueueRow key={item.reminder_id} item={item} title={titleById.get(item.responsibility_id)} />
                    ))}
                  </ul>
                </div>
              ) : null,
            )}
          </section>

          <section className="load__col" aria-labelledby="mine-h">
            <h2 id="mine-h" className="load__colhead label">
              Responsibilities you own
            </h2>
            {mine.length === 0 && !loading && (
              <p className="load__calm">You don't own any open responsibilities.</p>
            )}
            <ul className="rlist">
              {mine.map((r) => (
                <ResponsibilityRow key={r.id} r={r} />
              ))}
            </ul>
          </section>
        </div>
      )}

      {!nothing && (
        <p className="load__hint">
          Curious how a handoff really works?{" "}
          <button className="linkish" onClick={onJudge}>
            Play the 40-second demo
          </button>
          .
        </p>
      )}
    </div>
  );
}

function QueueRow({ item, title }: { item: GhostQueueItem; title?: string }) {
  return (
    <li className="qrow">
      <Link to={`/r/${item.responsibility_id}`} className="qrow__link">
        <span className="qrow__when mono">{relativeTime(item.scheduled_for)}</span>
        <span className="qrow__body">
          <span className="qrow__title">{title ?? "A responsibility"}</span>
          <span className="qrow__reason">{reminderLabel(item.reminder_type)}</span>
        </span>
        <span className="qrow__date mono">{calendarDate(item.scheduled_for)}</span>
      </Link>
    </li>
  );
}

function ResponsibilityRow({ r }: { r: ResponsibilitySummary }) {
  return (
    <li className="rrow">
      <Link to={`/r/${r.id}`} className="rrow__link">
        <span className="rrow__thread" aria-hidden />
        <span className="rrow__title">{r.title}</span>
        <span className="rrow__meta">
          {r.status !== "active" && <Pill tone={r.status}>{r.status.replace("_", " ")}</Pill>}
          <span className="rrow__ver mono">v{r.ownership_version}</span>
        </span>
      </Link>
    </li>
  );
}

function Quiet() {
  return (
    <motion.div
      className="quiet"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.6 }}
    >
      <svg className="quiet__thread" viewBox="0 0 120 60" fill="none" aria-hidden>
        <path d="M6 30H70" stroke="var(--hairline-strong)" strokeWidth="1.5" strokeDasharray="2 6" />
        <circle cx="6" cy="30" r="3" fill="var(--hairline-strong)" />
      </svg>
      <p className="quiet__line display">Nothing needs your attention right now.</p>
      <p className="quiet__sub">
        When you take something on — or someone hands it to you — it will appear here with only
        the next thing that matters.
      </p>
      <Link to="/new" className="load__capture">
        <span className="load__capture-plus" aria-hidden>
          +
        </span>
        Name a responsibility
      </Link>
    </motion.div>
  );
}

function bucketQueue(items: GhostQueueItem[]) {
  const now = Date.now();
  const out = { now: [] as GhostQueueItem[], soon: [] as GhostQueueItem[], later: [] as GhostQueueItem[] };
  for (const it of [...items].sort(
    (a, b) => new Date(a.scheduled_for).getTime() - new Date(b.scheduled_for).getTime(),
  )) {
    const t = new Date(it.scheduled_for).getTime();
    if (t - now <= DAY) out.now.push(it);
    else if (t - now <= 7 * DAY) out.soon.push(it);
    else out.later.push(it);
  }
  return out;
}

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return "Morning";
  if (h < 18) return "Afternoon";
  return "Evening";
}
