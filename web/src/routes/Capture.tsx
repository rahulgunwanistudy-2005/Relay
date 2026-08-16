import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import "./capture.css";
import { api } from "@/lib/api";
import { useSession } from "@/auth/session";
import { Banner, Button } from "@/components/ui";
import { ProvenancePip } from "@/components/OwnershipThread";
import { LIFECYCLE, LIFECYCLE_ORDER, calendarDate } from "@/lib/format";
import { revealNode } from "@/lib/motion";
import type { DraftResponse, LifecycleKind, Provenance } from "@/lib/types";

interface Node {
  kind: LifecycleKind;
  description: string;
  provenance: Provenance;
  isAssumption: boolean;
}

export function Capture() {
  const { householdId } = useSession();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const [text, setText] = useState("");
  const [phase, setPhase] = useState<"write" | "structuring" | "shape">("write");
  const [draft, setDraft] = useState<DraftResponse | null>(null);
  const [nodes, setNodes] = useState<Node[]>([]);
  const [standard, setStandard] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const present = useMemo(() => new Set(nodes.map((n) => n.kind)), [nodes]);
  const suggestable = LIFECYCLE_ORDER.filter((k) => !present.has(k));

  async function structure(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim() || !householdId) return;
    setError(null);
    setPhase("structuring");
    try {
      const d = await api.draft(householdId, text.trim());
      setDraft(d);
      setStandard(d.completion_standard ?? "");
      // Seed the shape with exactly what the backend parsed — nothing invented.
      const seeded: Node[] = d.steps.map((s) => ({
        kind: s.kind,
        description: s.description,
        provenance: s.provenance,
        isAssumption: s.is_assumption,
      }));
      setNodes(orderNodes(seeded));
      setPhase("shape");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not read that");
      setPhase("write");
    }
  }

  function addStage(kind: LifecycleKind) {
    setNodes((prev) =>
      orderNodes([
        ...prev,
        // Seed with the stage's plain-language gloss so it's a real, editable
        // obligation rather than an empty row that silently drops on save.
        {
          kind,
          description: LIFECYCLE[kind].gloss,
          provenance: "user_explicit",
          isAssumption: false,
        },
      ]),
    );
  }
  function updateNode(kind: LifecycleKind, patch: Partial<Node>) {
    setNodes((prev) => prev.map((n) => (n.kind === kind ? { ...n, ...patch } : n)));
  }
  function removeNode(kind: LifecycleKind) {
    setNodes((prev) => prev.filter((n) => n.kind !== kind));
  }

  async function create() {
    if (!householdId || !draft) return;
    const usable = nodes.filter((n) => n.description.trim());
    if (usable.length === 0) {
      setError("Keep at least one stage with a description.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const resp = await api.createResponsibility(householdId, {
        title: draft.title,
        domain: draft.domain,
        completion_standard: standard.trim() || null,
        target_at: draft.deadline_at,
        recurrence_rrule: draft.recurrence_rrule,
        steps: usable.map((n, i) => ({
          step_key: n.kind,
          kind: n.kind,
          description: n.description.trim(),
          ordering: i,
          due_at: n.kind === "execute" ? draft.deadline_at : null,
          provenance: n.provenance,
          is_assumption: n.isAssumption,
        })),
      });
      await qc.invalidateQueries({ queryKey: ["responsibilities", householdId] });
      navigate(`/r/${resp.id}`, { state: { justCreated: true } });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save");
      setSaving(false);
    }
  }

  return (
    <div className="cap">
      <AnimatePresence mode="wait">
        {phase !== "shape" ? (
          <motion.form
            key="write"
            className="cap__write"
            onSubmit={structure}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
          >
            <p className="label">Capture</p>
            <h1 className="cap__q display">What are you still carrying?</h1>
            <p className="cap__lead">
              Say it the way you'd say it to a partner. Relay reads it and lays out the
              work hiding behind it — so it can be handed over whole.
            </p>
            <textarea
              className="textarea cap__input"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="e.g. Can you take care of Maya's dentist appointment next month? We should compare a couple of pediatric dentists first."
              rows={4}
              autoFocus
              disabled={phase === "structuring"}
            />
            {error && <Banner tone="error">{error}</Banner>}
            <div className="cap__actions">
              <Button type="submit" pending={phase === "structuring"} disabled={!text.trim()}>
                {phase === "structuring" ? "Structuring responsibility…" : "Structure it"}
              </Button>
              {phase === "structuring" && (
                <span className="cap__structuring" aria-live="polite">
                  <span className="cap__thread-draw" aria-hidden />
                  Reading your words, not inventing any.
                </span>
              )}
            </div>
          </motion.form>
        ) : (
          <motion.div
            key="shape"
            className="cap__shape"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          >
            <button className="cap__back" onClick={() => setPhase("write")}>
              ← Rewrite
            </button>
            <p className="label">The responsibility</p>
            <h1 className="cap__title display">{draft?.title}</h1>

            <div className="cap__facts">
              {draft?.deadline_at && (
                <span className="cap__fact">
                  Due {calendarDate(draft.deadline_at)}
                  <ProvenancePip provenance={draft.field_provenance.deadline_at ?? "deterministic"} />
                </span>
              )}
              {draft?.recurrence_rrule && (
                <span className="cap__fact">Repeats · {draft.recurrence_rrule}</span>
              )}
              {draft?.people && draft.people.length > 0 && (
                <span className="cap__fact">People: {draft.people.join(", ")}</span>
              )}
              <span className="cap__fact cap__fact--src">via {draft?.provider.replace(/_/g, " ")}</span>
            </div>

            <div className="cap__shapehead">
              <h2 className="label">The hidden work</h2>
              <p className="cap__shapenote">
                Keep the stages that really apply. Each one is a place the old owner would
                otherwise stay on the hook.
              </p>
            </div>

            <div className="cap__nodes">
              {nodes.map((n, i) => (
                <motion.div
                  key={n.kind}
                  className="cnode"
                  custom={i}
                  variants={revealNode}
                  initial="hidden"
                  animate="show"
                >
                  <span className="cnode__rail" aria-hidden>
                    <span className="cnode__connector" />
                    <span className="cnode__dot" />
                  </span>
                  <div className="cnode__body">
                    <div className="cnode__head">
                      <span className="cnode__kind">{LIFECYCLE[n.kind].label}</span>
                      <ProvenancePip provenance={n.provenance} />
                      <label className="cnode__assume">
                        <input
                          type="checkbox"
                          checked={n.isAssumption}
                          onChange={(e) => updateNode(n.kind, { isAssumption: e.target.checked })}
                        />
                        assumption
                      </label>
                      <button
                        className="cnode__remove"
                        onClick={() => removeNode(n.kind)}
                        aria-label={`Remove ${LIFECYCLE[n.kind].label}`}
                      >
                        ✕
                      </button>
                    </div>
                    <input
                      className="cnode__input"
                      value={n.description}
                      placeholder={LIFECYCLE[n.kind].gloss}
                      onChange={(e) => updateNode(n.kind, { description: e.target.value })}
                    />
                  </div>
                </motion.div>
              ))}
            </div>

            {suggestable.length > 0 && (
              <div className="cap__add">
                <span className="cap__add-label">Add a stage:</span>
                {suggestable.map((k) => (
                  <button key={k} className="cap__add-btn" onClick={() => addStage(k)}>
                    + {LIFECYCLE[k].label}
                  </button>
                ))}
              </div>
            )}

            <label className="cap__standard">
              <span className="label">Done means</span>
              <input
                className="input"
                value={standard}
                placeholder="What has to be true for this to be truly finished?"
                onChange={(e) => setStandard(e.target.value)}
              />
            </label>

            {draft && draft.clarification_questions.length > 0 && (
              <div className="cap__open">
                <span className="label">Still open</span>
                <ul>
                  {draft.clarification_questions.map((q) => (
                    <li key={q}>{q}</li>
                  ))}
                </ul>
              </div>
            )}

            {error && <Banner tone="error">{error}</Banner>}
            <div className="cap__confirm">
              <Button onClick={create} pending={saving}>
                Make it a responsibility
              </Button>
              <span className="cap__confirm-note">
                Persists to Postgres. You can hand it over next.
              </span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function orderNodes(nodes: Node[]): Node[] {
  return [...nodes].sort(
    (a, b) => LIFECYCLE_ORDER.indexOf(a.kind) - LIFECYCLE_ORDER.indexOf(b.kind),
  );
}
