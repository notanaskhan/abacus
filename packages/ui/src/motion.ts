import { useEffect, useState, useSyncExternalStore } from "react";

// Motion hooks (F-05-T14; plan chapter 04 section 3.2 "motion.ts"). A media query in motion.css
// cuts CSS transitions and animations, but it cannot stop a component that decides in script to
// run one (a Web Animations loop, a word-by-word timer). So every animated component in the kit
// asks useReducedMotion() and, when it is true, renders no animation at all: no animation class,
// no timer. That is what leaves `document.getAnimations()` empty under `prefers-reduced-motion`.

export const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

function mediaQuery(): MediaQueryList | null {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return null;
  return window.matchMedia(REDUCED_MOTION_QUERY);
}

function subscribe(onChange: () => void): () => void {
  const query = mediaQuery();
  if (query === null) return () => undefined;
  query.addEventListener("change", onChange);
  return () => {
    query.removeEventListener("change", onChange);
  };
}

const getSnapshot = (): boolean => mediaQuery()?.matches ?? false;
// The server and the first client render agree on "motion allowed"; the store corrects at once.
const getServerSnapshot = (): boolean => false;

/** True while the person asks the system for reduced motion. Updates when the preference flips. */
export function useReducedMotion(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}

/**
 * Whether a component may animate: not under the system preference, and not when the caller
 * forces the still form (`still`, used by specimens and tests to draw the reduced-motion state).
 */
export function useMotion(still = false): boolean {
  const reduced = useReducedMotion();
  return !reduced && !still;
}

/** The time one word takes in a word-by-word reveal (chat kit C-10; ADR-066 has no token streaming). */
export const WORD_REVEAL_MS = 20;

/** Pieces of a text, each word with the white space after it, so joining them restores the text. */
export function wordsOf(text: string): string[] {
  return text.length === 0 ? [] : text.split(/(?<=\s)(?=\S)/u);
}

export interface WordReveal {
  /** The part of the text shown so far; the whole text when motion is off or the reveal is done. */
  text: string;
  done: boolean;
}

/**
 * Reveal an already-complete text word by word, 20 ms a word. It never reveals text a model is
 * still producing: the caller passes the whole, verified text (ADR-066). Under reduced motion, or
 * with `still`, the whole text is there on the first render and no timer runs. Render the result
 * through AgentText when the text came from an agent.
 */
export function useWordReveal(
  text: string,
  { msPerWord = WORD_REVEAL_MS, still = false }: { msPerWord?: number; still?: boolean } = {},
): WordReveal {
  const animate = useMotion(still);
  const words = wordsOf(text);
  const total = words.length;
  const [state, setState] = useState({ text, count: 0 });
  // A different text starts again from its first word.
  const count = state.text === text ? state.count : 0;
  const settled = !animate || count >= total;

  useEffect(() => {
    if (settled) return;
    const timer = setTimeout(() => {
      setState({ text, count: count + 1 });
    }, msPerWord);
    return () => {
      clearTimeout(timer);
    };
  }, [settled, text, count, msPerWord]);

  if (settled) return { text, done: true };
  return { text: words.slice(0, count).join(""), done: false };
}
