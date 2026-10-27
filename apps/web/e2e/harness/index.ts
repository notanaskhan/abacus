// The journey harness (F-04-T21; F-04 §3.8; ch. 04 §9.5): what a journey spec imports.
//
//   import { expect, test } from "../harness";
//
//   test("J02 1–2: Hannah opens the binder", async ({ journey }) => {
//     await journey.as("hannah-leclerc", "/binders");
//     await journey.step("J02 step 1: the binders index", async (page) => {
//       await expect(page.getByRole("heading", { name: "Binders" })).toBeVisible();
//     });
//   });
//
// Every `journey.step` runs inside `test.step`, then axe (serious and critical = 0; forced colors
// too on the first step) and INV-1 to INV-5 on the page as it stands. A step waits on state, never
// on time. The same spec runs in the fixture, fullstack, staging and canary projects; the persona
// adapter of the project signs the persona in.
import { test as base, type Page } from "@playwright/test";
import {
  type HarnessProject,
  type OpenOptions,
  type PersonaAdapter,
  adapterFor,
  harnessProject,
} from "./adapters";
import { axeStep } from "./axe";
import { type InvariantContext, assertInvariants } from "./invariants";
import { type Persona, type PersonaSlug, persona as personaOf } from "./personas";

export { expect } from "@playwright/test";
export { HARNESS_PROJECTS, type HarnessProject, registerHostedSignIn } from "./adapters";
export { assertStill, axeStep, settle } from "./axe";
export { AGENT_APPROVER, HUMAN_VERBS, assertInvariants, violations } from "./invariants";
export { DEMO_INSTANT, PERSONAS, type Persona, type PersonaSlug } from "./personas";

export interface StepScope {
  /** Names the persona must not see on this step (INV-3, INV-4). */
  outOfScope?: readonly string[];
  /** API paths that must answer 404 to the persona on this step (INV-3, INV-4). */
  probes?: readonly string[];
  /** Scope axe to an open overlay or region. */
  include?: string;
}

export class Journey {
  readonly project: HarnessProject;
  readonly adapter: PersonaAdapter;
  private who: Persona | null = null;
  private steps = 0;

  constructor(readonly page: Page) {
    this.project = harnessProject();
    this.adapter = adapterFor(this.project);
  }

  get persona(): Persona {
    if (this.who === null) throw new Error("journey.as(persona, path) first");
    return this.who;
  }

  /** Become `slug` and open `path` (an entry point; later steps click or use to.<ID>()). */
  async as(slug: PersonaSlug, path: string, options: OpenOptions = {}): Promise<void> {
    this.who = personaOf(slug);
    await this.adapter.open(this.page, this.who, path, options);
  }

  /** One journey step: run it, then axe and the five invariants. */
  async step(
    name: string,
    run: (page: Page) => Promise<void>,
    scope: StepScope = {},
  ): Promise<void> {
    await base.step(name, async () => {
      await run(this.page);
    });
    const first = this.steps === 0;
    this.steps += 1;
    await axeStep(this.page, name, {
      forcedColors: first,
      ...(scope.include === undefined ? {} : { include: scope.include }),
    });
    const ctx: InvariantContext = {
      step: name,
      persona: this.persona,
      adapter: this.adapter,
      ...(scope.outOfScope === undefined ? {} : { outOfScope: scope.outOfScope }),
      ...(scope.probes === undefined ? {} : { probes: scope.probes }),
    };
    await assertInvariants(this.page, ctx);
  }
}

export const test = base.extend<{ journey: Journey }>({
  journey: async ({ page }, use) => {
    await use(new Journey(page));
  },
});
