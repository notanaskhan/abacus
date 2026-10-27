// Binder export, full stack (A-01-T26; A-01 §10 `binder-export.fullstack.spec.ts`, kept with the
// journeys so the fullstack and staging projects run it; DEC-642). The steps need the live export
// routes, the worker and storage, so they are `test.fixme` until the S12 batch is deployed to
// staging (A-01 §10, M6); the backend suites (A-01-T18, T19, T22, T25) cover the same rules today.
import { test } from "../harness";

function owner(description: string): { annotation: { type: string; description: string } } {
  return { annotation: { type: "owner", description } };
}

const STAGING = owner("A-01 · A-01-T26 staging walk after the S12 deploy · M6, Fri Mar 5, 2027");

test.describe("Binder export (full stack)", () => {
  test.fixme(
    "export 1: Hannah exports Northwind's binder after a fresh MFA step-up and Undo inside 10 s cancels",
    STAGING,
    async ({ journey }) => {
      await journey.as("hannah-leclerc", "/audits");
    },
  );
  test.fixme(
    "export 2: the bundle downloads and every file matches its manifest SHA-256 (24 requests, 12 files)",
    STAGING,
    async ({ journey }) => {
      await journey.as("hannah-leclerc", "/audits");
    },
  );
  test.fixme(
    "export 3: a member walled from Northwind gets 404 and an agent context is refused",
    STAGING,
    async ({ journey }) => {
      await journey.as("hannah-leclerc", "/audits");
    },
  );
  test.fixme(
    "export 4: Margaret records the external release and Hannah archives against the final binder export",
    STAGING,
    async ({ journey }) => {
      await journey.as("margaret-okonkwo", "/audits");
    },
  );
});
