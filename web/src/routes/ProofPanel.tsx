import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { clockTime, memberName } from "@/lib/format";
import type { Member, OwnershipEvent, ProofOfRelief } from "@/lib/types";

const EVENT_VERB: Record<string, string> = {
  created: "Created",
  proposed: "Handoff proposed",
  accepted: "Accepted",
  declined: "Declined",
  transferred: "Ownership moved",
  escalated: "Escalated",
  completed: "Completed",
  archived: "Archived",
};

export function ProofPanel({
  proof,
  history,
  members,
  transferred,
}: {
  proof: ProofOfRelief | undefined;
  history: OwnershipEvent[] | undefined;
  members: Member[];
  transferred: boolean;
}) {
  const [openHistory, setOpenHistory] = useState(false);

  if (!transferred || !proof) {
    // Nothing has moved yet — don't manufacture a receipt.
    return (
      <div className="panel">
        <h2 className="label">Proof of relief</h2>
        <p className="panel__quiet">
          Once this is handed over and accepted, the receipt of exactly what moved appears
          here — drawn from real backend state.
        </p>
      </div>
    );
  }

  return (
    <div className="panel panel--proof">
      <h2 className="label">What moved</h2>
      <dl className="receipt">
        <Row n={proof.lifecycle_obligations_transferred} unit="lifecycle obligation" />
        <Row n={proof.reminders_rerouted} unit="future reminder" reroute />
        <Row n={proof.decision_points_transferred} unit="decision point" />
        {proof.recurrence_obligations_transferred > 0 && (
          <Row n={proof.recurrence_obligations_transferred} unit="recurring obligation" />
        )}
        <div className="receipt__row receipt__row--ver">
          <dt>Ownership</dt>
          <dd className="mono">
            v{proof.ownership_version_before} → v{proof.ownership_version_after}
          </dd>
        </div>
        <div className="receipt__row receipt__row--to">
          <dt>Now owned by</dt>
          <dd>{memberName(members, proof.new_owner_membership_id)}</dd>
        </div>
      </dl>

      <p className="receipt__boomerang">
        No Boomerang · future reminders for this belong to{" "}
        {memberName(members, proof.new_owner_membership_id)}, not you.
      </p>

      <button
        className="receipt__history-toggle"
        onClick={() => setOpenHistory((v) => !v)}
        aria-expanded={openHistory}
      >
        {openHistory ? "Hide" : "Show"} ownership history
      </button>
      <AnimatePresence initial={false}>
        {openHistory && history && (
          <motion.ol
            className="trace"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.24 }}
          >
            {history.map((e) => (
              <li className="trace__row" key={e.id}>
                <span className="trace__time mono">{clockTime(e.created_at)}</span>
                <span className="trace__verb">{EVENT_VERB[e.event_type] ?? e.event_type}</span>
                <span className="trace__who">
                  {e.previous_owner_membership_id && e.new_owner_membership_id
                    ? `${memberName(members, e.previous_owner_membership_id)} → ${memberName(
                        members,
                        e.new_owner_membership_id,
                      )}`
                    : e.new_owner_membership_id
                      ? memberName(members, e.new_owner_membership_id)
                      : memberName(members, e.actor_membership_id)}
                </span>
              </li>
            ))}
          </motion.ol>
        )}
      </AnimatePresence>
    </div>
  );
}

function Row({ n, unit, reroute }: { n: number; unit: string; reroute?: boolean }) {
  return (
    <div className="receipt__row">
      <dt className="mono">{n}</dt>
      <dd>
        {unit}
        {n === 1 ? "" : "s"} {reroute ? "rerouted" : "transferred"}
      </dd>
    </div>
  );
}
