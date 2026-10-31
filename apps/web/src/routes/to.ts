import type { OverlayRef } from "../app-core/overlays";
import { MANIFEST } from "./manifest";

// Typed screen links (F-04-T14; chapter 04 section 2.6). `to.CLI02({ clientId })` gives the
// `to` and `params` of a TanStack <Link>, from the screen's manifest entry:
//
//   <Link {...to.CLI02({ clientId })} preload="intent">…</Link>
//
// It is the only way to link to a screen (eslint bans string `to=` in src/screens/**), which is how
// link-contract.test.ts sees every designed link. A screen gets a builder once its entry has a
// path, so linking to an unrouted screen does not compile.

type Manifest = typeof MANIFEST;

/** "CLI-02" -> "CLI02". */
type BuilderName<I extends string> = I extends `${infer M}-${infer N}` ? `${M}${N}` : I;

/** The `$param` names of a route path. */
type ParamNames<P extends string> = P extends `${string}$${infer Name}/${infer Rest}`
  ? Name | ParamNames<`/${Rest}`>
  : P extends `${string}$${infer Name}`
    ? Name
    : never;

type Target<P extends string> = [ParamNames<P>] extends [never]
  ? { readonly to: P }
  : { readonly to: P; readonly params: Readonly<Record<ParamNames<P>, string>> };

type Builder<P extends string> = [ParamNames<P>] extends [never]
  ? () => Target<P>
  : (params: Readonly<Record<ParamNames<P>, string>>) => Target<P>;

type PathOf<I extends keyof Manifest> = Manifest[I]["path"];

export type ScreenLinks = {
  readonly [
    I in keyof Manifest as PathOf<I> extends string ? BuilderName<I & string> : never
  ]: PathOf<I> extends string ? Builder<PathOf<I>> : never;
};

function builder(path: string) {
  const names = [...path.matchAll(/\$([A-Za-z0-9_]+)/g)].map((m) => m[1]);
  if (names.length === 0) return () => ({ to: path });
  return (params: Readonly<Record<string, string>>) => ({ to: path, params });
}

function build(): ScreenLinks {
  const links: Record<string, ReturnType<typeof builder>> = {};
  for (const [id, entry] of Object.entries(MANIFEST)) {
    const path: string | null = entry.path;
    if (path !== null) links[id.replace("-", "")] = builder(path);
  }
  return links as unknown as ScreenLinks;
}

/** One builder per routed screen, named by its ID without the hyphen (CLI-02 -> to.CLI02). */
export const to: ScreenLinks = build();

type Link = { readonly to: string; readonly params?: Readonly<Record<string, string>> };

/** A builder's target as an href: each `$name` filled from its params, then the search, if any. */
export function hrefOf(target: Link, search: Readonly<Record<string, string>> = {}): string {
  const params = target.params ?? {};
  const path = target.to.replace(/\$(\w+)/gu, (_m, name: string) =>
    encodeURIComponent(params[name] ?? ""),
  );
  const query = new URLSearchParams(search).toString();
  return query === "" ? path : `${path}?${query}`;
}

/** Typed overlay links (DEC-1273): a screen with no path opens as a layer over its host
 * (`?ov=<key>:<args>`, app-core/overlays), so link-contract.test.ts sees `ov.<ID>(…)` as it sees
 * `to.<ID>(…)`. One builder per overlay screen a built screen opens. */
export const ov = {
  /** SHL-16, the checkpoint drawer over its target (`?ov=checkpoints:<type>:<id>`). */
  SHL16: (type: string, id: string): OverlayRef => ({ key: "checkpoints", args: [type, id] }),
  /** SHL-11, the decision sheet over its host (`?ov=decision:<cardId>`; P-04-T52). */
  SHL11: (cardId: string): OverlayRef => ({ key: "decision", args: [cardId] }),
  /** SHL-12, the sign-off sheet over its target (`?ov=signoff:<type>:<id>[:<level>]`; P-04-T52). */
  SHL12: (type: string, id: string, level?: string): OverlayRef => ({
    key: "signoff",
    args: level === undefined ? [type, id] : [type, id, level],
  }),
  /** SHL-14, the request composer drawer over its host (`?ov=request:<id|new>:<binderId>`). */
  SHL14: (requestId: string, binderId: string): OverlayRef => ({
    key: "request",
    args: [requestId, binderId],
  }),
  /** TAX-09, a return's tax-engine sync over TAX-01 or TAX-02 (`?ov=engine-sync:<returnId>`). */
  TAX09: (returnId: string): OverlayRef => ({ key: "engine-sync", args: [returnId] }),
  /** SIG-02, the envelope builder over its host (`?ov=envelope:<envelopeId>`; N-02-T37: ENG-04's
   * Send opens the C7 draft it created, prefilled). */
  SIG02: (envelopeId: string): OverlayRef => ({ key: "envelope", args: [envelopeId] }),
} as const;
