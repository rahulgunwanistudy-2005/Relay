// One ease, one spring language. Components import from here rather than each
// inventing its own physics.

import type { Transition, Variants } from "framer-motion";

export const EASE = [0.22, 0.61, 0.36, 1] as const;

export const spring: Transition = { type: "spring", stiffness: 220, damping: 30, mass: 0.9 };
export const gentle: Transition = { duration: 0.24, ease: EASE };
export const panel: Transition = { duration: 0.3, ease: EASE };

// REVEAL — a lifecycle node resolves out of the thread line, not a generic fade-up.
export const revealNode: Variants = {
  hidden: { opacity: 0, x: -10, filter: "blur(1px)" },
  show: (i: number) => ({
    opacity: 1,
    x: 0,
    filter: "blur(0px)",
    transition: { delay: 0.06 * i, duration: 0.42, ease: EASE },
  }),
};

export function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}
