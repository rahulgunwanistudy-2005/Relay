import { useCallback, useEffect, useRef, useState } from "react";

export interface Scene {
  id: string;
  label: string;
  durationMs: number;
  caption: string;
}

export interface DirectorState {
  index: number;
  scene: Scene;
  progress: number; // 0..1 within the current scene
  overall: number; // 0..1 across the whole timeline
  playing: boolean;
  done: boolean;
}

export interface DirectorControls {
  play: () => void;
  pause: () => void;
  toggle: () => void;
  next: () => void;
  prev: () => void;
  restart: () => void;
  seekTo: (index: number) => void;
}

/**
 * A deterministic scene director. One rAF loop accumulates elapsed time and
 * advances scenes by their declared duration — no scattered setTimeouts. Every
 * scene boundary is reproducible; only real data fills the visuals.
 */
export function useDirector(scenes: Scene[], autoPlay = true): [DirectorState, DirectorControls] {
  const total = scenes.reduce((s, x) => s + x.durationMs, 0);
  const offsets = scenes.reduce<number[]>((acc, _s, i) => {
    acc[i] = (acc[i - 1] ?? 0) + (i === 0 ? 0 : scenes[i - 1].durationMs);
    return acc;
  }, []);

  const [index, setIndex] = useState(0);
  const [progress, setProgress] = useState(0);
  const [playing, setPlaying] = useState(autoPlay);
  const [done, setDone] = useState(false);

  const rafRef = useRef<number | null>(null);
  const lastRef = useRef<number | null>(null);
  const elapsedRef = useRef(0); // elapsed within current scene

  const stop = () => {
    if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;
    lastRef.current = null;
  };

  const setScene = useCallback((i: number) => {
    elapsedRef.current = 0;
    setProgress(0);
    setIndex(i);
    setDone(false);
  }, []);

  useEffect(() => {
    if (!playing) {
      stop();
      return;
    }
    const tick = (now: number) => {
      if (lastRef.current == null) lastRef.current = now;
      const dt = now - lastRef.current;
      lastRef.current = now;
      elapsedRef.current += dt;
      const dur = scenes[index]?.durationMs ?? 1;
      if (elapsedRef.current >= dur) {
        if (index >= scenes.length - 1) {
          setProgress(1);
          setPlaying(false);
          setDone(true);
          stop();
          return;
        }
        elapsedRef.current = 0;
        setProgress(0);
        setIndex((i) => i + 1);
      } else {
        setProgress(elapsedRef.current / dur);
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return stop;
  }, [playing, index, scenes]);

  const controls: DirectorControls = {
    play: () => {
      if (done) {
        setScene(0);
      }
      setPlaying(true);
    },
    pause: () => setPlaying(false),
    toggle: () => (playing ? setPlaying(false) : (done ? (setScene(0), setPlaying(true)) : setPlaying(true))),
    next: () => setScene(Math.min(index + 1, scenes.length - 1)),
    prev: () => setScene(Math.max(index - 1, 0)),
    restart: () => {
      setScene(0);
      setPlaying(true);
    },
    seekTo: (i: number) => setScene(Math.max(0, Math.min(i, scenes.length - 1))),
  };

  const overall = total > 0 ? (offsets[index] + progress * (scenes[index]?.durationMs ?? 0)) / total : 0;

  return [
    { index, scene: scenes[index], progress, overall, playing, done },
    controls,
  ];
}
