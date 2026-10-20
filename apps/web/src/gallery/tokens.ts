// /components/tokens (SPEC-048 AC-11): every token in theme.css, and for each colour its contrast
// on card, shell and nested under both ladders. The AA ladder is what theme.css holds (DEC-11);
// the reference ladder is the handoff's lighter values, which `?contrast=reference` restores for
// parity runs. Only the overrides below differ between the ladders.
import themeCss from "@abacus/ui/theme.css?raw";

export type Rgba = readonly [number, number, number, number];

export interface Token {
  /** The custom property without its prefix: `ink-3`. */
  name: string;
  /** `color`, `radius`, `shadow`, `text`, `font` ... */
  group: string;
  value: string;
}

/** The handoff's values where they differ from the AA ladder (ADR-155 decision 5; DEC-115). */
export const REFERENCE_OVERRIDES: Readonly<Record<string, string>> = {
  "ink-3": "rgba(43, 31, 23, 0.54)",
  "match-ink": "rgb(146, 83, 162)", // #9253A2 in the handoff
};

/** The surfaces a text token must read on. */
export const SURFACES = ["card", "shell", "nested"] as const;

/** The `@theme` block's declarations, in file order. `--x-*: initial` resets are not tokens. */
export function parseTokens(css: string = themeCss): Token[] {
  const bare = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const open = bare.indexOf("@theme");
  if (open < 0) return [];
  const start = bare.indexOf("{", open) + 1;
  let depth = 1;
  let end = start;
  while (end < bare.length && depth > 0) {
    const ch = bare[end];
    if (ch === "{") depth += 1;
    if (ch === "}") depth -= 1;
    end += 1;
  }
  const body = bare.slice(start, end - 1);
  const tokens: Token[] = [];
  for (const m of body.matchAll(/--([a-z0-9-]+)\s*:\s*([^;]+);/g)) {
    const [, full, raw] = m;
    if (full === undefined || raw === undefined) continue;
    const group = full.split("-")[0] ?? full;
    tokens.push({
      name: full.slice(group.length + 1),
      group,
      value: raw.replace(/\s+/g, " ").trim(),
    });
  }
  return tokens;
}

export function parseColor(value: string): Rgba | null {
  const hex = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(value.trim());
  if (hex?.[1] !== undefined) {
    const h = hex[1].length === 3 ? hex[1].replace(/./g, "$&$&") : hex[1];
    const n = Number.parseInt(h, 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255, 1];
  }
  const fn = /^rgba?\(([^)]+)\)$/i.exec(value.trim());
  if (fn?.[1] !== undefined) {
    const p = fn[1]
      .split(/[\s,/]+/)
      .filter(Boolean)
      .map(Number);
    const [r, g, b, a = 1] = p;
    if (r === undefined || g === undefined || b === undefined || p.some(Number.isNaN)) return null;
    return [r, g, b, a];
  }
  return null;
}

/** The colour as a solid, composited over `over` (a solid backdrop). */
export function solid(color: Rgba, over: Rgba): [number, number, number] {
  const [r, g, b, a] = color;
  return [
    Math.round(r * a + over[0] * (1 - a)),
    Math.round(g * a + over[1] * (1 - a)),
    Math.round(b * a + over[2] * (1 - a)),
  ];
}

export function hex(rgb: readonly [number, number, number]): string {
  return `#${rgb.map((c) => c.toString(16).padStart(2, "0")).join("")}`;
}

function luminance(rgb: readonly [number, number, number]): number {
  const [r, g, b] = rgb.map((c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  }) as [number, number, number];
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** WCAG 2.x contrast ratio of two solids, 1 to 21. */
export function contrastRatio(
  a: readonly [number, number, number],
  b: readonly [number, number, number],
): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
}

export interface ColorRow {
  name: string;
  /** As written in theme.css (AA ladder). */
  value: string;
  /** The reference ladder's value; equal to `value` unless overridden. */
  referenceValue: string;
  /** Effective solid on card, per ladder. */
  solid: { aa: string; reference: string };
  /** Contrast ratio per surface, per ladder. */
  contrast: {
    aa: Record<(typeof SURFACES)[number], number>;
    reference: Record<(typeof SURFACES)[number], number>;
  };
}

function surfaceSolids(
  tokens: readonly Token[],
): Record<(typeof SURFACES)[number], [number, number, number]> {
  const find = (n: string): [number, number, number] => {
    const c = parseColor(tokens.find((t) => t.group === "color" && t.name === n)?.value ?? "");
    return c === null ? [255, 255, 255] : [c[0], c[1], c[2]];
  };
  return { card: find("card"), shell: find("shell"), nested: find("nested") };
}

/** Every colour token with its contrast under both ladders; unparseable colours are skipped. */
export function colorRows(tokens: readonly Token[] = parseTokens()): ColorRow[] {
  const surfaces = surfaceSolids(tokens);
  const white: Rgba = [...surfaces.card, 1];
  const rows: ColorRow[] = [];
  for (const t of tokens) {
    if (t.group !== "color") continue;
    const referenceValue = REFERENCE_OVERRIDES[t.name] ?? t.value;
    const aa = parseColor(t.value);
    const ref = parseColor(referenceValue);
    if (aa === null || ref === null) continue;
    const per = (c: Rgba): Record<(typeof SURFACES)[number], number> => {
      const out = {} as Record<(typeof SURFACES)[number], number>;
      for (const s of SURFACES) out[s] = contrastRatio(solid(c, [...surfaces[s], 1]), surfaces[s]);
      return out;
    };
    rows.push({
      name: t.name,
      value: t.value,
      referenceValue,
      solid: { aa: hex(solid(aa, white)), reference: hex(solid(ref, white)) },
      contrast: { aa: per(aa), reference: per(ref) },
    });
  }
  return rows;
}
