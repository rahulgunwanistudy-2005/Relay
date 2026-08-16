import { motion } from "framer-motion";
import { OwnershipThread, type ThreadNode } from "@/components/OwnershipThread";
import { firstName } from "@/lib/format";
import type { JudgeTrace } from "./useJudgeTrace";

export function JudgeStage({
  sceneId,
  trace,
  reduced,
}: {
  sceneId: string;
  trace: JudgeTrace;
  reduced: boolean;
}) {
  const nodes: ThreadNode[] = (trace.responsibility.current_cycle?.steps ?? []).map((s) => ({
    id: s.id,
    kind: s.kind,
    description: s.description,
    provenance: s.provenance,
    status: s.status,
    isAssumption: s.is_assumption,
  }));
  const source = firstName(trace.sourceName);
  const recipient = firstName(trace.recipientName);
  const moved = sceneId === "transfer" || sceneId === "boomerang" || sceneId === "proof" || sceneId === "relief";
  const fade = reduced ? { duration: 0.001 } : { duration: 0.5 };

  return (
    <div className="jstage">
      {sceneId === "burden" && (
        <motion.div className="jscene jscene--center" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={fade}>
          <div className="jburden">
            <span className="jburden__name display">{source}</span>
            <div className="jburden__thread" aria-hidden>
              <span className="jburden__anchor" />
              {[0, 1, 2, 3].map((i) => (
                <motion.span
                  key={i}
                  className="jburden__tick"
                  initial={{ opacity: 0, y: -6 }}
                  animate={{ opacity: 1 - i * 0.18, y: 0 }}
                  transition={{ delay: reduced ? 0 : 0.25 + i * 0.25 }}
                />
              ))}
            </div>
            <span className="jburden__label label">still carrying it, silently</span>
          </div>
        </motion.div>
      )}

      {sceneId === "sentence" && (
        <motion.div className="jscene jscene--center" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={fade}>
          <p className="jquote-mark" aria-hidden>“</p>
          <p className="jsentence display">{trace.sentence}</p>
          <p className="jsentence__sub label">one ordinary sentence</p>
        </motion.div>
      )}

      {sceneId === "xray" && (
        <motion.div className="jscene jscene--xray" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={fade}>
          <p className="jscene__eyebrow label">{trace.sentence}</p>
          <OwnershipThread nodes={nodes} reveal={!reduced} tone="active" compact />
        </motion.div>
      )}

      {(sceneId === "contract" || moved) && (
        <motion.div className="jscene jscene--owners" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={fade}>
          <div className="jowners">
            <JOwner name={source} lit={!moved} quiet={moved} caption={moved ? "nothing scheduled" : "handing over"} />
            <div className="jowners__track" aria-hidden>
              <div className={`jowners__line ${moved ? "is-crossed" : ""}`} />
              <motion.span
                className="jowners__bead"
                initial={false}
                animate={{ left: moved ? "100%" : "0%", x: moved ? "-100%" : "0%" }}
                transition={reduced ? { duration: 0.001 } : { duration: 0.85, ease: [0.65, 0, 0.35, 1] }}
              />
            </div>
            <JOwner name={recipient} lit={moved} arrived={moved} caption={moved ? "now owns it" : "receiving"} />
          </div>

          {sceneId === "contract" && (
            <div className="jcontract">
              <span className="jcontract__resp display">{trace.responsibility.title}</span>
              {trace.responsibility.completion_standard && (
                <span className="jcontract__term">Done means: {trace.responsibility.completion_standard}</span>
              )}
              <span className="jcontract__term">
                {nodes.length} lifecycle stage{nodes.length === 1 ? "" : "s"} · consent required before it moves
              </span>
            </div>
          )}

          {sceneId === "boomerang" && (
            <div className="jboom">
              <div className="jboom__side jboom__side--quiet">
                <span className="label">{source}</span>
                <p>Nothing from this is scheduled here anymore.</p>
              </div>
              <div className="jboom__side jboom__side--active">
                <span className="label">{recipient}</span>
                <p>
                  <span className="mono jboom__num">{trace.proof.reminders_rerouted}</span> future
                  reminder{trace.proof.reminders_rerouted === 1 ? "" : "s"} now belong here.
                </p>
              </div>
            </div>
          )}

          {sceneId === "proof" && (
            <div className="jproof">
              <ProofLine n={trace.proof.lifecycle_obligations_transferred} unit="lifecycle obligation" />
              <ProofLine n={trace.proof.reminders_rerouted} unit="future reminder" reroute />
              <ProofLine n={trace.proof.decision_points_transferred} unit="decision point" />
              {trace.proof.recurrence_obligations_transferred > 0 && (
                <ProofLine n={trace.proof.recurrence_obligations_transferred} unit="recurring obligation" />
              )}
              <p className="jproof__ver mono">
                ownership v{trace.proof.ownership_version_before} → v{trace.proof.ownership_version_after}
              </p>
            </div>
          )}

          {sceneId === "relief" && (
            <p className="jrelief">
              {recipient} owns it now. {source}'s space is quiet — genuinely nothing left to remember.
            </p>
          )}
        </motion.div>
      )}
    </div>
  );
}

function JOwner({
  name,
  lit,
  quiet,
  arrived,
  caption,
}: {
  name: string;
  lit: boolean;
  quiet?: boolean;
  arrived?: boolean;
  caption: string;
}) {
  return (
    <div className={`jowner ${lit ? "jowner--lit" : ""} ${quiet ? "jowner--quiet" : ""}`}>
      <span className={`jowner__dot ${arrived ? "jowner__dot--arrived" : ""}`} aria-hidden />
      <span className="jowner__name display">{name}</span>
      <span className="jowner__caption label">{caption}</span>
    </div>
  );
}

function ProofLine({ n, unit, reroute }: { n: number; unit: string; reroute?: boolean }) {
  return (
    <p className="jproof__line">
      <span className="mono jproof__num">{n}</span> {unit}
      {n === 1 ? "" : "s"} {reroute ? "rerouted" : "transferred"}
    </p>
  );
}
