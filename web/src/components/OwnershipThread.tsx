import { motion } from "framer-motion";
import "./thread.css";
import { LIFECYCLE, PROVENANCE_META } from "@/lib/format";
import { revealNode } from "@/lib/motion";
import type { LifecycleKind, Provenance, StepStatus } from "@/lib/types";

export interface ThreadNode {
  id: string;
  kind: LifecycleKind;
  description: string;
  provenance: Provenance;
  status?: StepStatus;
  isAssumption?: boolean;
  due?: string | null;
}

type Tone = "active" | "quiet" | "settled" | "pending";

interface Props {
  ownerLabel?: string | null;
  nodes: ThreadNode[];
  reveal?: boolean; // stage the reveal (X-Ray moment)
  tone?: Tone;
  onToggle?: (node: ThreadNode) => void;
  compact?: boolean;
  headingId?: string;
}

/**
 * A continuous representation of one responsibility across its lifecycle.
 * The thread is the spine; each lifecycle stage is a node attached to it.
 * The SVG spine is decorative (aria-hidden); the ordered list is the truth
 * screen readers read.
 */
export function OwnershipThread({
  ownerLabel,
  nodes,
  reveal = false,
  tone = "active",
  onToggle,
  compact = false,
  headingId,
}: Props) {
  return (
    <div className={`thread thread--${tone} ${compact ? "thread--compact" : ""}`}>
      {ownerLabel !== undefined && ownerLabel !== null && (
        <div className="thread__anchor">
          <span className="thread__anchor-dot" aria-hidden />
          <span className="thread__anchor-name">{ownerLabel}</span>
          <span className="thread__anchor-caption label">carries this</span>
        </div>
      )}
      <ol className="thread__list" aria-labelledby={headingId}>
        {nodes.map((node, i) => {
          const meta = LIFECYCLE[node.kind];
          const done = node.status === "done";
          const revealProps = reveal
            ? { custom: i, variants: revealNode, initial: "hidden" as const, animate: "show" as const }
            : {};
          return (
            <motion.li
              key={node.id}
              className={`tnode tnode--${node.status ?? "pending"} ${
                node.isAssumption ? "tnode--assumption" : ""
              }`}
              {...revealProps}
            >
              <span className="tnode__rail" aria-hidden>
                <span className="tnode__connector" />
                <span className="tnode__dot" />
              </span>
              <div className="tnode__body">
                <div className="tnode__head">
                  <span className="tnode__kind">{meta.label}</span>
                  <ProvenancePip provenance={node.provenance} />
                  {node.isAssumption && <span className="tnode__assume">assumption</span>}
                  {done && <span className="tnode__done">done</span>}
                </div>
                <p className={`tnode__desc ${done ? "tnode__desc--done" : ""}`}>
                  {node.description}
                </p>
                {!compact &&
                  meta.gloss.trim().toLowerCase() !== node.description.trim().toLowerCase() && (
                    <p className="tnode__gloss">{meta.gloss}</p>
                  )}
                {onToggle && node.status && (
                  <button
                    type="button"
                    className="tnode__toggle"
                    onClick={() => onToggle(node)}
                    aria-pressed={done}
                  >
                    {done ? "Reopen" : "Mark done"}
                  </button>
                )}
              </div>
            </motion.li>
          );
        })}
      </ol>
    </div>
  );
}

export function ProvenancePip({ provenance }: { provenance: Provenance }) {
  const meta = PROVENANCE_META[provenance];
  return (
    <span className={`pip pip--${provenance}`} title={meta.label}>
      <span className="pip__glyph" aria-hidden>
        {provenance === "user_explicit" ? "▪" : provenance === "ai_inferred" ? "◇" : "·"}
      </span>
      {meta.short}
    </span>
  );
}
