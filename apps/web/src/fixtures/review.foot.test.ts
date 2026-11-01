// P-04-T34: every SHL-09 to SHL-16 artboard renders from typed fixtures. The 44 artboards of the
// handoff's six READMEs, each seen by its viewer at its instant, each answer a schema-valid body on
// a route the OpenAPI document serves with that status, and each scenario's handlers answer what
// the artboard draws. Figures that foot are asserted in contracts/review-grammar.test.ts.
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import type { FixtureRequest } from "../app-core/fixture-mode";
import { reviewArtboards, reviewHandlers, reviewScenarios } from "./handlers/review";
import { validateSchema } from "./schema-check";
import { getSeed, meFor } from "./seed";
import {
  REVIEW_ARTBOARDS,
  REVIEW_CLOCKS,
  type ReviewFrame,
  type ReviewScreen,
  SHL16,
  cp6Detail,
} from "./seed/review";

const here = dirname(fileURLToPath(import.meta.url));
const PATHS = (
  JSON.parse(
    readFileSync(
      join(here, "..", "..", "..", "..", "packages", "api-client", "openapi.json"),
      "utf8",
    ),
  ) as { paths: Record<string, Record<string, { responses: Record<string, unknown> }>> }
).paths;

/** The handoff's artboards per screen (its README tables; a prime is named as its screenshot). */
const HANDOFF: Record<ReviewScreen, string[]> = {
  "SHL-09": ["a", "b", "c", "d", "e", "f"],
  "SHL-10": ["a", "b", "c", "d", "e", "ep", "f", "g"],
  "SHL-11": ["a", "b", "c", "d", "e", "f", "g", "h"],
  "SHL-12": ["a", "ap", "b", "c", "d", "e", "f", "g", "h"],
  "SHL-15": ["a", "ap", "app", "b", "c", "d", "e"],
  "SHL-16": ["a", "b", "c", "d", "e", "f"],
};
const SCREENS = Object.keys(HANDOFF) as ReviewScreen[];

function request(frame: ReviewFrame, persona: string): FixtureRequest {
  const [method = "GET", path = ""] = frame.route.split(" ");
  return {
    method,
    path,
    params: { ...frame.params },
    // A frame that names its record in the query (SHL-12 f's eligibility) is asked with it.
    query: new URLSearchParams(frame.query ?? {}),
    body: null,
    persona,
  };
}

describe("the 44 review artboards (P-04-T34)", () => {
  it("every artboard of the six handoff READMEs has its frames, in the handoff's order", () => {
    expect(REVIEW_ARTBOARDS).toHaveLength(44);
    for (const screen of SCREENS) {
      expect(
        reviewArtboards(screen).map((a) => a.state),
        screen,
      ).toEqual(HANDOFF[screen]);
    }
    for (const a of REVIEW_ARTBOARDS)
      expect(a.frames.length, `${a.screen} ${a.state}`).toBeGreaterThan(0);
  });

  it("each is drawn at E0 or a snapshot (Sep 14, Sep 24, Oct 1, Oct 6)", () => {
    const clocks = new Set<string>(Object.values(REVIEW_CLOCKS));
    for (const a of REVIEW_ARTBOARDS)
      expect(clocks.has(a.clock), `${a.screen} ${a.state}`).toBe(true);
    const at = (screen: ReviewScreen, state: string) =>
      REVIEW_ARTBOARDS.find((a) => a.screen === screen && a.state === state)?.clock;
    expect(at("SHL-16", "a")).toBe("2026-09-14T09:24:00-05:00"); // E0
    expect(at("SHL-12", "a")).toBe("2026-09-14T09:41:00-05:00");
    expect(at("SHL-12", "e")).toBe("2026-09-24T14:15:00-05:00");
    expect(at("SHL-10", "a")).toBe("2026-10-01T09:24:00-05:00");
    expect(at("SHL-11", "d")).toBe("2026-10-06T09:24:00-05:00");
  });

  it("each viewer is a person of the Brightwater Hale seed", () => {
    const seed = getSeed();
    for (const a of REVIEW_ARTBOARDS) {
      if (a.viewer !== null) expect(meFor(seed, a.viewer), `${a.screen} ${a.state}`).toBeDefined();
    }
  });

  it("every answer is its schema, on a route the API serves with that status", () => {
    for (const a of REVIEW_ARTBOARDS) {
      for (const frame of a.frames) {
        const where = `${a.screen} ${a.state} ${frame.route}`;
        const [method = "", path = ""] = frame.route.split(" ");
        const responses = PATHS[path]?.[method.toLowerCase()]?.responses;
        expect(responses, where).toBeDefined();
        expect(Object.keys(responses ?? {}), where).toContain(String(frame.status));
        expect(validateSchema(frame.schema, frame.body), where).toEqual([]);
      }
    }
  });

  it("every request an artboard sends is its schema, on a route the API serves", () => {
    for (const a of REVIEW_ARTBOARDS) {
      for (const sent of a.requests) {
        const where = `${a.screen} ${a.state} ${sent.route}`;
        const [method = "", path = ""] = sent.route.split(" ");
        expect(PATHS[path]?.[method.toLowerCase()], where).toBeDefined();
        expect(validateSchema(sent.schema, sent.body), where).toEqual([]);
      }
    }
  });
});

describe("the review scenarios serve what each artboard draws", () => {
  for (const screen of SCREENS) {
    it(`${screen}: one scenario per artboard, seen by its viewer at its instant`, async () => {
      const scenarios = reviewScenarios(screen);
      expect(Object.keys(scenarios)).toEqual(HANDOFF[screen]);
      for (const a of reviewArtboards(screen)) {
        const scenario = scenarios[a.state];
        expect(scenario?.clock).toBe(a.clock);
        if (a.viewer !== null) expect(scenario?.persona).toBe(a.viewer);
        for (const frame of a.frames) {
          const handler = scenario?.handlers[frame.route];
          const response = await handler?.(request(frame, scenario?.persona ?? ""));
          expect(response?.status, `${a.state} ${frame.route}`).toBe(frame.status);
          expect(await response?.json(), `${a.state} ${frame.route}`).toEqual(frame.body);
        }
      }
    });
  }

  it("with no artboard, a record's route answers that record and another id is 404", async () => {
    const handlers = reviewHandlers();
    const detail = handlers["GET /v1/checkpoints/{checkpoint_id}"];
    const ask = (checkpoint_id: string) =>
      detail?.({
        method: "GET",
        path: `/v1/checkpoints/${checkpoint_id}`,
        params: { checkpoint_id },
        query: new URLSearchParams(),
        body: null,
        persona: "samuel-ito",
      });
    expect(await (await ask(cp6Detail.checkpoint.id))?.json()).toEqual(cp6Detail);
    expect((await ask("00000000-0000-4000-8000-000000009999"))?.status).toBe(404);
    const list = await handlers["GET /v1/checkpoints"]?.(
      request({ route: "GET /v1/checkpoints", schema: "", status: 200, body: null }, "samuel-ito"),
    );
    expect(await list?.json()).toEqual(SHL16.a);
  });
});
