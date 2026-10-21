// Banned product terms (F-02-T09; DEC-19): generated from docs/architecture/scope-guards.yaml into
// scope-guards.gen.json by abacus_tools.quality.scope_guards, and found in string literals, JSX
// text and template text. Shared by apps/web and packages/ui; the backend twin is scope_guards.py.
import guards from "./scope-guards.gen.json" with { type: "json" };

const escape = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/'/g, "\\'");

/** `no-restricted-syntax` entries, one per banned term, naming the rule and the replacement. */
export function scopeTermSyntax() {
  return guards.bannedTerms.flatMap(({ term, use, rule }) => {
    const pattern = `/${escape(term)}/`;
    const message = `"${term}" is banned (${rule}, scope guards): use ${use}.`;
    return [
      { selector: `Literal[value=${pattern}]`, message },
      { selector: `JSXText[value=${pattern}]`, message },
      { selector: `TemplateElement[value.raw=${pattern}]`, message },
    ];
  });
}

/** The 13 firm bar labels, in order (D4). */
export const NAV = guards.nav;
