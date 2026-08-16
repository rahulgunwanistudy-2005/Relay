import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import "./contract.css";
import { api } from "@/lib/api";
import { useSession } from "@/auth/session";
import { useMembers, useResponsibility } from "@/lib/queries";
import { OwnershipThread, type ThreadNode } from "@/components/OwnershipThread";
import { Banner, Button } from "@/components/ui";
import { calendarDate, firstName, memberName } from "@/lib/format";
import { prefersReducedMotion } from "@/lib/motion";
import type { AcceptResponse, HandoffContract } from "@/lib/types";

type Phase = "review" | "sealing" | "moving" | "settled";

export function Contract() {
  const { contractId } = useParams();
  const { user, householdId } = useSession();
  const qc = useQueryClient();
  const navigate = useNavigate();

  const [contract, setContract] = useState<HandoffContract | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const members = useMembers(householdId);
  const resp = useResponsibility(contract?.responsibility_id);

  const [phase, setPhase] = useState<Phase>("review");
  const [result, setResult] = useState<AcceptResponse | null>(null);
  const [actionErr, setActionErr] = useState<string | null>(null);
  const idemRef = useRef(`accept-${crypto.randomUUID()}`);

  useEffect(() => {
    let alive = true;
    if (!contractId) return;
    api
      .getHandoff(contractId)
      .then((c) => alive && setContract(c))
      .catch((e) => alive && setLoadErr(e instanceof Error ? e.message : "Not found"));
    return () => {
      alive = false;
    };
  }, [contractId]);

  const myMembershipId = members.data?.find((m) => m.user_id === user?.id)?.id ?? null;
  const sourceName = memberName(members.data, contract?.source_owner_membership_id ?? null);
  const recipientName = memberName(members.data, contract?.proposed_owner_membership_id ?? null);
  const amRecipient =
    !!contract && !!myMembershipId && contract.proposed_owner_membership_id === myMembershipId;
  const alreadyResolved = !!contract && contract.status !== "pending";

  const nodes: ThreadNode[] = useMemo(
    () =>
      (resp.data?.current_cycle?.steps ?? []).map((s) => ({
        id: s.id,
        kind: s.kind,
        description: s.description,
        provenance: s.provenance,
        status: s.status,
        isAssumption: s.is_assumption,
      })),
    [resp.data?.current_cycle?.steps],
  );

  async function accept() {
    if (!contractId) return;
    setActionErr(null);
    setPhase("sealing");
    try {
      const r = await api.acceptHandoff(contractId, idemRef.current);
      setResult(r);
      // Server has confirmed. Only now does ownership visibly move.
      if (prefersReducedMotion()) {
        setPhase("settled");
      } else {
        setPhase("moving");
      }
      qc.invalidateQueries();
    } catch (err) {
      setActionErr(err instanceof Error ? err.message : "Could not accept");
      setPhase("review");
    }
  }

  async function decline() {
    if (!contractId) return;
    try {
      await api.declineHandoff(contractId);
      qc.invalidateQueries();
      navigate("/inbox");
    } catch (err) {
      setActionErr(err instanceof Error ? err.message : "Could not decline");
    }
  }

  // Advance from the migration animation to the settled receipt.
  useEffect(() => {
    if (phase !== "moving") return;
    const t = setTimeout(() => setPhase("settled"), 1200);
    return () => clearTimeout(t);
  }, [phase]);

  if (loadErr)
    return (
      <div className="contract__wrap">
        <Banner tone="error">This contract isn't reachable: {loadErr}</Banner>
      </div>
    );
  if (!contract || resp.isLoading)
    return <div className="contract__loading">Opening the contract…</div>;

  const owned = phase === "settled" || phase === "moving";
  const litSide: "source" | "recipient" = owned ? "recipient" : "source";

  return (
    <div className="contract__wrap">
      <p className="label">Ownership contract</p>
      <h1 className="contract__q display">
        {amRecipient ? "What exactly am I agreeing to own?" : "A handoff between two people"}
      </h1>

      {/* The two owners with the responsibility thread between them. */}
      <div className={`xfer xfer--${phase}`}>
        <OwnerColumn
          name={sourceName}
          role="Handing it over"
          lit={litSide === "source"}
          quiet={owned}
        />
        <div className="xfer__track" aria-hidden>
          <div className={`xfer__line ${owned ? "is-crossed" : ""}`} />
          <motion.div
            className="xfer__bead"
            initial={false}
            animate={{ left: owned ? "100%" : "0%", x: owned ? "-100%" : "0%" }}
            transition={{ duration: 0.9, ease: [0.65, 0, 0.35, 1] }}
          />
          <span className="xfer__boundary" />
        </div>
        <OwnerColumn
          name={recipientName}
          role={amRecipient ? "You" : "Receiving it"}
          lit={litSide === "recipient"}
          quiet={false}
          arrived={owned}
        />
      </div>

      <p className="xfer__status" aria-live="polite">
        {phase === "review" &&
          "Ownership has not moved. Review the whole shape below before you decide."}
        {phase === "sealing" && "Committing the transfer…"}
        {phase === "moving" && "Ownership is moving…"}
        {phase === "settled" &&
          result &&
          `Ownership moved to ${firstName(recipientName)}. ${result.reminders_rerouted} future reminder${
            result.reminders_rerouted === 1 ? "" : "s"
          } rerouted.`}
      </p>

      {phase === "settled" && result ? (
        <SettledReceipt
          result={result}
          recipientName={recipientName}
          sourceName={sourceName}
          onDone={() => navigate(`/r/${contract.responsibility_id}`)}
        />
      ) : (
        <>
          <div className="contract__body">
            <div className="contract__scope">
              <h2 className="label contract__scopehead">The responsibility</h2>
              <p className="contract__resp display">{resp.data?.title}</p>
              <div className="contract__terms">
                {resp.data?.completion_standard && (
                  <Term label="Done means">{resp.data.completion_standard}</Term>
                )}
                {resp.data?.current_cycle?.target_at && (
                  <Term label="Due">{calendarDate(resp.data.current_cycle.target_at)}</Term>
                )}
                {resp.data?.recurrence && (
                  <Term label="Recurs">{resp.data.recurrence.rrule}</Term>
                )}
                <Term label="You inherit">
                  the whole lifecycle below, plus every future reminder it generates
                </Term>
              </div>
              <OwnershipThread nodes={nodes} tone="pending" compact />
            </div>
          </div>

          {actionErr && <Banner tone="error">{actionErr}</Banner>}

          {alreadyResolved ? (
            <Banner tone="info">
              This contract is already {contract.status}. Nothing to do here.
            </Banner>
          ) : amRecipient ? (
            <div className="contract__actions">
              <Button variant="ghost" onClick={decline} disabled={phase !== "review"}>
                Decline
              </Button>
              <Button onClick={accept} pending={phase === "sealing"}>
                Accept ownership
              </Button>
            </div>
          ) : (
            <Banner tone="info">
              Only {firstName(recipientName)} can accept this — it was proposed to them.
            </Banner>
          )}
        </>
      )}
    </div>
  );
}

function OwnerColumn({
  name,
  role,
  lit,
  quiet,
  arrived,
}: {
  name: string;
  role: string;
  lit: boolean;
  quiet: boolean;
  arrived?: boolean;
}) {
  return (
    <div className={`ocol ${lit ? "ocol--lit" : ""} ${quiet ? "ocol--quiet" : ""}`}>
      <span className={`ocol__dot ${arrived ? "ocol__dot--arrived" : ""}`} aria-hidden />
      <span className="ocol__name">{name}</span>
      <span className="ocol__role label">{quiet ? "Nothing scheduled here" : role}</span>
    </div>
  );
}

function Term({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="term">
      <span className="term__label label">{label}</span>
      <span className="term__value">{children}</span>
    </div>
  );
}

function SettledReceipt({
  result,
  recipientName,
  sourceName,
  onDone,
}: {
  result: AcceptResponse;
  recipientName: string;
  sourceName: string;
  onDone: () => void;
}) {
  return (
    <motion.div
      className="settled"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.15, duration: 0.4 }}
    >
      <div className="settled__proof">
        <h2 className="label">What just moved</h2>
        <p className="settled__line mono">
          {result.reminders_rerouted} future reminder{result.reminders_rerouted === 1 ? "" : "s"}{" "}
          rerouted
        </p>
        <p className="settled__line mono">ownership v{result.ownership_version - 1} → v{result.ownership_version}</p>
        <p className="settled__boomerang">
          {firstName(sourceName)} is no longer this responsibility's reminder system.
          Everything future belongs to {firstName(recipientName)}. That's No Boomerang.
        </p>
      </div>
      <Button onClick={onDone}>See the responsibility</Button>
    </motion.div>
  );
}
