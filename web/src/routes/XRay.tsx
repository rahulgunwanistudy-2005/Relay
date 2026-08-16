import { useMemo, useState } from "react";
import { useLocation, useParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import "./xray.css";
import { api } from "@/lib/api";
import { useSession } from "@/auth/session";
import { useHistory, useMembers, useProof, useResponsibility } from "@/lib/queries";
import { OwnershipThread, type ThreadNode } from "@/components/OwnershipThread";
import { HandoffPanel } from "./HandoffPanel";
import { ProofPanel } from "./ProofPanel";
import { Pill } from "@/components/ui";
import { calendarDate, memberName } from "@/lib/format";

export function XRay() {
  const { id } = useParams();
  const location = useLocation() as { state?: { justCreated?: boolean } };
  const justCreated = !!location.state?.justCreated;
  const { user, householdId } = useSession();
  const qc = useQueryClient();

  const resp = useResponsibility(id);
  const members = useMembers(householdId);
  const proof = useProof(id);
  const history = useHistory(id);

  const myMembershipId = members.data?.find((m) => m.user_id === user?.id)?.id ?? null;
  const r = resp.data;
  const isOwner = !!r && r.current_owner_membership_id === myMembershipId;
  const transferred = proof.data?.transferred ?? false;
  const ownerName = memberName(members.data, r?.current_owner_membership_id ?? null);

  const nodes: ThreadNode[] = useMemo(
    () =>
      (r?.current_cycle?.steps ?? []).map((s) => ({
        id: s.id,
        kind: s.kind,
        description: s.description,
        provenance: s.provenance,
        status: s.status,
        isAssumption: s.is_assumption,
        due: s.due_at,
      })),
    [r?.current_cycle?.steps],
  );

  const [busyStep, setBusyStep] = useState<string | null>(null);
  async function toggle(node: ThreadNode) {
    if (!id) return;
    setBusyStep(node.id);
    try {
      if (node.status === "done") await api.reopenStep(id, node.id);
      else await api.completeStep(id, node.id);
      await qc.invalidateQueries({ queryKey: ["responsibility", id] });
    } finally {
      setBusyStep(null);
    }
  }

  if (resp.isLoading) return <div className="xray__loading">Opening the responsibility…</div>;
  if (resp.isError || !r)
    return <div className="xray__loading">This responsibility isn't reachable from here.</div>;

  return (
    <div className={`xray ${justCreated ? "xray--fresh" : ""}`}>
      <header className="xray__head">
        <div className="xray__crumb label">
          {r.domain} · scope v{r.scope_version} · ownership v{r.ownership_version}
        </div>
        <h1 className="xray__title display">{r.title}</h1>
        <div className="xray__ownerline">
          <span className="xray__owner">
            <span className="xray__owner-dot" data-quiet={!isOwner && transferred} aria-hidden />
            {isOwner ? "You carry this" : `${ownerName} carries this`}
          </span>
          {r.status !== "active" && <Pill tone={r.status}>{r.status.replace(/_/g, " ")}</Pill>}
          {r.completion_standard && (
            <span className="xray__standard">Done means: {r.completion_standard}</span>
          )}
        </div>
      </header>

      <div className="xray__grid">
        <section className="xray__thread" aria-labelledby="xray-lc">
          <h2 id="xray-lc" className="label xray__sectionhead">
            What this responsibility contains
          </h2>
          <OwnershipThread
            nodes={nodes}
            tone={transferred && !isOwner ? "quiet" : "active"}
            onToggle={isOwner ? toggle : undefined}
            headingId="xray-lc"
          />
          {busyStep && <span className="sr-only">Updating step…</span>}
          {r.recurrence && (
            <p className="xray__recur">
              Recurs · {r.recurrence.rrule}
              {r.recurrence.next_materialization_at &&
                ` · next ${calendarDate(r.recurrence.next_materialization_at)}`}
            </p>
          )}
        </section>

        <aside className="xray__rail">
          <HandoffPanel
            responsibility={r}
            members={members.data ?? []}
            myMembershipId={myMembershipId}
          />
          <ProofPanel
            proof={proof.data}
            history={history.data}
            members={members.data ?? []}
            transferred={transferred}
          />
        </aside>
      </div>

      {transferred && !isOwner && (
        <motion.p
          className="xray__relief"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3, duration: 0.6 }}
        >
          Nothing from this responsibility is scheduled for you anymore. It belongs to{" "}
          {ownerName}.
        </motion.p>
      )}
    </div>
  );
}
