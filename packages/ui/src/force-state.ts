// forceState (plan 04 section 5.2 rule 3): every interactive component takes a `forceState`, so the
// gallery and the screenshot tests draw each state without a pointer. A forced state sets
// `data-force="<state>"` on the element, and the component's classes (and base.css for `focus`)
// style that attribute exactly as they style the real state. `disabled` is not forced: it is the
// attribute.

/** The states a specimen can hold a component in. A component takes the ones that apply to it. */
export type ForceState = "hover" | "focus" | "pressed" | "open" | "loading";

/** The attribute a forced state sets (nothing when none is forced). */
export function forceAttr(state: ForceState | undefined): { "data-force"?: ForceState } {
  return state === undefined ? {} : { "data-force": state };
}
