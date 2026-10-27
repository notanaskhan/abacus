// J20 group audit (A-01-T26; A-01 §10): only the entry step is in A-01's scope: "+ New audit" on
// AUD-01 opens ENG-03 with Audit & assurance preselected. AUD-01's "New audit" is still "Not built
// yet" (its copy), and group audits are A-09's, so every step is `test.fixme` naming its owner.
import { test } from "../harness";

function owner(description: string): { annotation: { type: string; description: string } } {
  return { annotation: { type: "owner", description } };
}

test.describe("J20 group audit", () => {
  test.fixme(
    'j20 1 (entry): "+ New audit" opens ENG-03 with Audit & assurance preselected',
    owner("K-04 · ENG-14 and A-09 · AUD-02 h · S20 onward"),
    async ({ journey }) => {
      await journey.as("hannah-leclerc", "/audits");
    },
  );
});
