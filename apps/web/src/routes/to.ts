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
