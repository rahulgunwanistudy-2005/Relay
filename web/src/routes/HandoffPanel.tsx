import { useState } from "react";
import { Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Banner, Button } from "@/components/ui";
import { firstName } from "@/lib/format";
import type { Member, Responsibility } from "@/lib/types";

const CID_HINT = "relay.lastContract."; // client hint only; recipient inbox is authoritative

export function HandoffPanel({
  responsibility: r,
  members,
  myMembershipId,
}: {
  responsibility: Responsibility;
  members: Member[];
  myMembershipId: string | null;
}) {
  const qc = useQueryClient();
  const isOwner = r.current_owner_membership_id === myMembershipId;
  const others = members.filter((m) => m.id !== r.current_owner_membership_id && m.is_active);

  const [target, setTarget] = useState<string>("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [contractId, setContractId] = useState<string | null>(
    () => localStorage.getItem(CID_HINT + r.id),
  );

  async function propose() {
    if (!target) return;
    setPending(true);
    setError(null);
    try {
      const c = await api.proposeHandoff(r.id, target);
      localStorage.setItem(CID_HINT + r.id, c.id);
      setContractId(c.id);
      await qc.invalidateQueries({ queryKey: ["responsibility", r.id] });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not propose");
    } finally {
      setPending(false);
    }
  }

  // Not the owner — this belongs to someone else.
  if (!isOwner) {
    return (
      <div className="panel">
        <h2 className="label">Ownership</h2>
        <p className="panel__quiet">
          You don't own this responsibility, so there's nothing here for you to hand over.
        </p>
      </div>
    );
  }

  if (r.status === "transfer_pending") {
    return (
      <div className="panel panel--pending">
        <h2 className="label">Handoff proposed</h2>
        <p className="panel__pending">
          Ownership hasn't moved yet. It's waiting for the other person to open the contract
          and accept.
        </p>
        {contractId ? (
          <Link className="panel__contract-link" to={`/handoff/${contractId}`}>
            Open the contract →
          </Link>
        ) : (
          <p className="panel__quiet">
            The recipient will find it under <strong>Incoming</strong>.
          </p>
        )}
      </div>
    );
  }

  if (others.length === 0) {
    return (
      <div className="panel">
        <h2 className="label">Hand it over</h2>
        <p className="panel__quiet">
          Invite someone to your household first — then you can transfer this whole
          responsibility to them.
        </p>
        <Link className="panel__contract-link" to="/household">
          Invite someone →
        </Link>
      </div>
    );
  }

  return (
    <div className="panel">
      <h2 className="label">Hand it over</h2>
      <p className="panel__quiet">
        Transfer the whole shape of this — not just the visible task. The other person reviews
        the scope and consents before anything moves.
      </p>
      <div className="handoff__pick" role="radiogroup" aria-label="Choose recipient">
        {others.map((m) => (
          <button
            key={m.id}
            role="radio"
            aria-checked={target === m.id}
            className={`handoff__member ${target === m.id ? "is-on" : ""}`}
            onClick={() => setTarget(m.id)}
          >
            <span className="handoff__member-name">{m.display_name}</span>
            <span className="handoff__member-role">{m.role}</span>
          </button>
        ))}
      </div>
      {error && <Banner tone="error">{error}</Banner>}
      <Button variant="primary" onClick={propose} pending={pending} disabled={!target}>
        {target
          ? `Propose to ${firstName(others.find((m) => m.id === target)?.display_name ?? "")}`
          : "Choose a recipient"}
      </Button>
    </div>
  );
}
