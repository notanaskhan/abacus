// The C3 review grammar in fixture mode (P-04-T34; docs/contracts/review-grammar.md): every SHL-09,
// SHL-10, SHL-11, SHL-12, SHL-15 and SHL-16 artboard's answers, served on the C3 routes from the
// typed frames in seed/review.ts. One artboard's scenario serves that artboard's frames, seen by
// its viewer at its instant; with no artboard, each route answers the first artboard that draws it,
// narrowed to the record the path names, so `make dev-fixtures` can open any of them.
//
// Nothing here decides, signs or approves (INV-1): a write route answers the frame the artboard
// shows after the person's act.

import {
  type FixtureHandler,
  type FixtureRequest,
  type Scenario,
  defineScenarios,
  json,
} from "../../app-core/fixture-mode";
import { DEFAULT_PERSONA } from "../handlers";
import { seedScenario } from "../scenario";
import {
  REVIEW_ARTBOARDS,
  type ReviewArtboard,
  type ReviewFrame,
  type ReviewScreen,
} from "../seed/review";

const NOT_FOUND = { detail: "not_found" };

/** Whether a frame answers this request: its route, and the record its path names (if any). */
function answers(frame: ReviewFrame, request: FixtureRequest): boolean {
  const params = frame.params ?? {};
  return Object.entries(params).every(([key, value]) => request.params[key] === value);
}

/** One route's handler over the frames that draw it, first match wins; none: 404. */
function serve(frames: readonly ReviewFrame[]): FixtureHandler {
  return (request) => {
    const found = frames.find((f) => answers(f, request));
    return found === undefined ? json(NOT_FOUND, 404) : json(found.body, found.status);
  };
}

/** The C3 handlers for one artboard, or (none given) every artboard's frames by route. */
export function reviewHandlers(
  artboard?: ReviewArtboard,
  artboards: readonly ReviewArtboard[] = REVIEW_ARTBOARDS,
): Record<string, FixtureHandler> {
  const frames = artboard === undefined ? artboards.flatMap((a) => a.frames) : artboard.frames;
  const byRoute = new Map<string, ReviewFrame[]>();
  for (const frame of frames) {
    byRoute.set(frame.route, [...(byRoute.get(frame.route) ?? []), frame]);
  }
  const handlers: Record<string, FixtureHandler> = {};
  for (const [route, drawn] of byRoute) handlers[route] = serve(drawn);
  return handlers;
}

/** One screen's artboards, in the handoff's order. */
export function reviewArtboards(screen: ReviewScreen): ReviewArtboard[] {
  return REVIEW_ARTBOARDS.filter((a) => a.screen === screen);
}

/** A screen's fixture scenarios, one per artboard: E0's handlers with the artboard's C3 answers on
 * top, seen by its viewer (the default persona where the artboard names none) at its instant. */
export function reviewScenarios(screen: ReviewScreen): Record<string, Scenario> {
  return scenariosOf(reviewArtboards(screen));
}

/** Scenarios for artboards outside the handoff's 44 (P-04-T47's SHL-16 import variant), built
 * the same way: E0's handlers with each artboard's answers on top. */
export function scenariosOf(artboards: readonly ReviewArtboard[]): Record<string, Scenario> {
  const e0 = seedScenario();
  const scenarios: Record<string, Scenario> = {};
  for (const artboard of artboards) {
    scenarios[artboard.state] = {
      ...e0,
      state: artboard.state,
      persona: artboard.viewer ?? DEFAULT_PERSONA,
      clock: artboard.clock,
      handlers: { ...e0.handlers, ...reviewHandlers(artboard) },
    };
  }
  return defineScenarios(scenarios);
}
