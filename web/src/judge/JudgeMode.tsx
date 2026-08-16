import { useEffect, useMemo } from "react";
import { motion } from "framer-motion";
import "./judge.css";
import { useSession } from "@/auth/session";
import { useJudgeTrace } from "./useJudgeTrace";
import { useDirector, type Scene } from "./director";
import { JudgeStage } from "./JudgeStage";
import { prefersReducedMotion } from "@/lib/motion";
import { Button } from "@/components/ui";

const SCENES: Scene[] = [
  { id: "burden", label: "The burden", durationMs: 4000, caption: "The task moved. The remembering didn't." },
  { id: "sentence", label: "One sentence", durationMs: 5000, caption: "It starts as one ordinary sentence." },
  { id: "xray", label: "X-Ray", durationMs: 6000, caption: "The hidden work appears." },
  { id: "contract", label: "Scope & consent", durationMs: 5000, caption: "Ownership has scope — and needs consent." },
  { id: "transfer", label: "The handoff", durationMs: 6000, caption: "Responsibility moves." },
  { id: "boomerang", label: "No Boomerang", durationMs: 6000, caption: "Future obligations follow the owner. No Boomerang." },
  { id: "proof", label: "Proof", durationMs: 5000, caption: "Proof, not promises — every number is real." },
  { id: "relief", label: "Relief", durationMs: 4000, caption: "Relay transfers responsibility. Not chores." },
];

export function JudgeMode({ onExit }: { onExit: () => void }) {
  const { householdId } = useSession();
  const traceQ = useJudgeTrace(householdId);
  const reduced = prefersReducedMotion();

  const ready = traceQ.data?.status === "ready";
  const scenes = useMemo(() => SCENES, []);
  const [state, controls] = useDirector(scenes, false);

  // Autoplay only once a real trace is ready.
  useEffect(() => {
    if (ready) controls.restart();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready]);

  // Keyboard transport.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === " ") {
        e.preventDefault();
        controls.toggle();
      } else if (e.key === "ArrowRight") controls.next();
      else if (e.key === "ArrowLeft") controls.prev();
      else if (e.key === "r" || e.key === "R") controls.restart();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [controls]);

  return (
    <motion.div
      className="judge"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.35 }}
      role="dialog"
      aria-modal="true"
      aria-label="Relay demonstration"
    >
      <div className="judge__scrim" onClick={onExit} />
      <div className="judge__frame">
        <header className="judge__top">
          <span className="judge__chapter label">
            {ready ? `${state.index + 1} / ${scenes.length} · ${state.scene.label}` : "Relay"}
          </span>
          <button className="judge__exit" onClick={onExit} aria-label="Exit demonstration">
            Exit ✕
          </button>
        </header>

        <div className="judge__stagewrap">
          {traceQ.isLoading && <Message title="Gathering a real trace…" />}

          {traceQ.data?.status === "empty" && (
            <Message
              title="Nothing to demonstrate yet"
              body="Capture a responsibility and hand it to someone. Judge Mode replays a real transfer — it won't stage a fake one."
              action={<Button onClick={onExit}>Close</Button>}
            />
          )}
          {traceQ.data?.status === "none" && (
            <Message
              title="Judge Mode needs a completed handoff"
              body="There's a responsibility, but no accepted transfer to show yet. Propose one and have the other person accept it — then this replays the real thing."
              action={<Button onClick={onExit}>Close</Button>}
            />
          )}
          {traceQ.isError && (
            <Message
              title="Relay can't verify this responsibility right now"
              body="The backend didn't answer. Judge Mode won't fabricate the story while it's offline."
              action={<Button onClick={onExit}>Close</Button>}
            />
          )}

          {traceQ.data?.status === "ready" && (
            <JudgeStage sceneId={state.scene.id} trace={traceQ.data.trace} reduced={reduced} />
          )}
        </div>

        {ready && (
          <footer className="judge__controls">
            <div className="judge__progress" role="progressbar" aria-valuenow={Math.round(state.overall * 100)}>
              <div className="judge__progress-fill" style={{ width: `${state.overall * 100}%` }} />
              <div className="judge__ticks">
                {scenes.map((s, i) => (
                  <button
                    key={s.id}
                    className={`judge__tick ${i === state.index ? "is-on" : ""}`}
                    onClick={() => controls.seekTo(i)}
                    aria-label={`Scene ${i + 1}: ${s.label}`}
                  />
                ))}
              </div>
            </div>
            <p className="judge__caption" aria-live="polite">
              {state.scene.caption}
            </p>
            <div className="judge__transport">
              <button onClick={controls.prev} aria-label="Previous scene">
                ⤺ Prev
              </button>
              <button className="judge__play" onClick={controls.toggle}>
                {state.playing ? "❚❚ Pause" : state.done ? "↻ Replay" : "▶ Play"}
              </button>
              <button onClick={controls.next} aria-label="Next scene">
                Next ⤼
              </button>
              <button onClick={controls.restart} aria-label="Restart">
                Restart
              </button>
            </div>
          </footer>
        )}
      </div>
    </motion.div>
  );
}

function Message({
  title,
  body,
  action,
}: {
  title: string;
  body?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="judge__message">
      <p className="judge__message-title display">{title}</p>
      {body && <p className="judge__message-body">{body}</p>}
      {action}
    </div>
  );
}
