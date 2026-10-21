// Deterministic randomness for the interim seed (F-04-T05; SPEC-307 AC-1). No unseeded source and no
// wall clock: every value comes from a string label, so two builds are identical and adding one
// record never reshuffles the others. mulberry32 over an xmur3 string hash.

function hasher(text: string): () => number {
  let h = 1779033703 ^ text.length;
  for (let i = 0; i < text.length; i += 1) {
    h = Math.imul(h ^ text.charCodeAt(i), 3432918353);
    h = (h << 13) | (h >>> 19);
  }
  return () => {
    h = Math.imul(h ^ (h >>> 16), 2246822507);
    h = Math.imul(h ^ (h >>> 13), 3266489909);
    h ^= h >>> 16;
    return h >>> 0;
  };
}

/** A seeded generator in [0, 1). */
export function mulberry32(seed: number): () => number {
  let a = seed | 0;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export class Rng {
  private readonly draw: () => number;

  constructor(namespace: string) {
    this.draw = mulberry32(hasher(namespace)());
  }

  next(): number {
    return this.draw();
  }

  /** An integer in [min, max]. */
  int(min: number, max: number): number {
    return min + Math.floor(this.draw() * (max - min + 1));
  }

  pick<T>(items: readonly T[]): T {
    const item = items[Math.floor(this.draw() * items.length)];
    if (item === undefined) throw new Error("pick from an empty list");
    return item;
  }

  chance(probability: number): boolean {
    return this.draw() < probability;
  }
}

const hex8 = (n: number): string => n.toString(16).padStart(8, "0");

/** A UUID-shaped id (version 4 layout) derived from a label: the same label is the same id. */
export function stableId(label: string): string {
  const next = hasher(`id:${label}`);
  const s = hex8(next()) + hex8(next()) + hex8(next()) + hex8(next());
  const variant = "89ab".charAt(parseInt(s.charAt(16), 16) & 3);
  return `${s.slice(0, 8)}-${s.slice(8, 12)}-4${s.slice(13, 16)}-${variant}${s.slice(17, 20)}-${s.slice(20, 32)}`;
}
