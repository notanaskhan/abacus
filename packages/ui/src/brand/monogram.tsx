import type { JSX } from "react";
import { AgentMonogram } from "../icons/custom";

// The Accrued monogram and the Agent's avatar (Foundations 01 Brand, F-05-T14). The tile is drawn
// once, as the registry's AgentMonogram glyph (icons/custom.tsx: espresso square, radius 28%,
// Geist 500 "a" at 0.62 of the side, olive posted dot); this file only fixes the sizes the brand
// allows and gives the Agent's use of it a name of its own.

/** The sizes the brand draws (favicon and agent tile 16, sign-in 28, 88 for the construction). */
export const MONOGRAM_SIZES = [16, 20, 28, 34, 44, 88] as const;
export type MonogramSize = (typeof MONOGRAM_SIZES)[number];
/** The smallest the brand allows. Below it the dot and the "a" merge. */
export const MONOGRAM_MIN = 16;

export interface MonogramProps {
  size?: MonogramSize;
  /** Accessible name, only where nothing beside the mark says "Accrued". Otherwise hidden. */
  label?: string;
  className?: string;
}

/**
 * The Accrued monogram. It appears on firm sign-in, the favicon, the command-palette and
 * firm-menu footers and the tenant console (PLT-01), and never in the firm app's chrome. The size
 * type stops at 16; a value forced below it is raised to it.
 */
export function Monogram({ size = 28, label, className }: MonogramProps): JSX.Element {
  const side = Math.max(size, MONOGRAM_MIN);
  return (
    <AgentMonogram
      size={side}
      data-brand="monogram"
      {...(label === undefined ? {} : { label })}
      {...(className === undefined ? {} : { className })}
    />
  );
}

export interface AgentAvatarProps {
  /** Accessible name, only where no text beside the avatar says whose work it is. Otherwise hidden. */
  label?: string;
  className?: string;
}

/**
 * The Accrued Agent's avatar: the 16px monogram tile, and nothing else. The Agent is never drawn
 * as a person, so there are no initials, no tint and no photo; work it prepared is attributed in
 * words, "‹person› via Agent" (formatActor, F-05-T30). The chat thread draws no avatars at all
 * (C-10); this is for rows and cards that name the Agent.
 */
export function AgentAvatar({ label, className }: AgentAvatarProps): JSX.Element {
  return (
    <AgentMonogram
      size={MONOGRAM_MIN}
      data-actor="agent"
      {...(label === undefined ? {} : { label })}
      {...(className === undefined ? {} : { className })}
    />
  );
}
