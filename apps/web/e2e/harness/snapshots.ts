// TASK-7814: the full-stack project runs against one seeded snapshot at a time. The nightly loads
// E0 (`make seed-demo SNAPSHOT=E0`) and runs every journey but the `@sep24` ones; it then reloads
// at 2026-09-24T10:20 with the slices those steps read and runs only them
// (ABACUS_SEED_SNAPSHOT=2026-09-24T10:20, `--grep @sep24`). A step whose data the scenario
// timeline holds only from that snapshot on is tagged `@sep24` and declares it with
// `seededAt`, so it is `fixme` on a full stack loaded at another snapshot, never faked at E0.
import { test } from "@playwright/test";
import type { HarnessProject } from "./adapters";

declare const process: { env: Record<string, string | undefined> };

/** The snapshot `make seed-demo` loaded for the fullstack project (default E0). */
export const SEED_SNAPSHOT = process.env.ABACUS_SEED_SNAPSHOT ?? "E0";

/** Sep 24, 10:20 AM CT (epochs.py): AUD-11 f's clock; the sampling slice's draws are in. */
export const SEP_24_SNAPSHOT = "2026-09-24T10:20";

/** The tag of a step the nightly runs on the Sep 24 seed (`--grep @sep24`). */
export const SEP_24_PASS = { tag: "@sep24" } as const;

/** A full-stack step that reads data the timeline holds from `snapshot` on: `fixme` on a full
 * stack seeded at any other snapshot. Other projects are the spec's own concern. */
export function seededAt(project: HarnessProject, snapshot: string, why: string): void {
  test.fixme(
    project === "fullstack" && SEED_SNAPSHOT !== snapshot,
    `the full stack is seeded at ${SEED_SNAPSHOT}; ${why} (ABACUS_SEED_SNAPSHOT=${snapshot})`,
  );
}
