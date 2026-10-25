import type { JSX } from "react";
import { AgentText } from "../agent-text";
import { SCREENING_LABELS, ScreeningCard } from "../components/screening/ScreeningCard";
import { Held, Row, Sheet } from "./frame";

// C-34 ScreeningCard (P-06-T22): the four states on the handoff's SHL-20 copy (spec.md, verbatim).
// The flag reasons are agent text, so they go through AgentText here as in the product.

const REQUEST =
  "Support for 40 subsequent disbursements (SURL) · expected period Jun 1 – Sep 18, 2026";
const PROVENANCE =
  "Screened by Accrued Agent · screener@v3 · 2 s · instructions inside files are never followed";
const Q = SCREENING_LABELS.questions;

const noop = (): void => undefined;

export function ScreeningCardSpecimen(): JSX.Element {
  return (
    <Sheet title="ScreeningCard" meta="C-34 · 420 wide · never a confidence">
      <Row name="Flagged" spec="two checks, flagged files with View and Return…">
        <Held name="flagged">
          <ScreeningCard
            verdict="flagged"
            time="Sep 26, 10:12 AM"
            request={REQUEST}
            checks={[
              {
                key: "right_document",
                question: Q.right_document,
                verdict: "flag",
                answer: "29 of 31 files answer their payment. 2 do not.",
              },
              {
                key: "right_period",
                question: Q.right_period,
                verdict: "pass",
                answer: "All other files are dated inside Jun 1 – Sep 18, 2026.",
              },
            ]}
            flagged={[
              {
                id: "f1",
                name: "Granite Rock Logistics — August statement.pdf",
                reason: (
                  <AgentText
                    inline
                    text="This is a statement, not the invoice for payment #40188 ($23,940)."
                  />
                ),
                onView: noop,
                onReturn: noop,
              },
            ]}
            primary={{ label: "Draft follow-up", onClick: noop }}
            secondary={{ label: "Rerun", icon: "rotate-ccw", onClick: noop }}
            provenance={PROVENANCE}
            onClose={noop}
          />
        </Held>
      </Row>
      <Row name="Passed" spec="olive ✓, the total line">
        <Held name="passed">
          <ScreeningCard
            verdict="passed"
            time="Sep 28, 9:05 AM"
            request={REQUEST}
            checks={[
              { key: "right_document", question: Q.right_document, verdict: "pass", answer: null },
              { key: "right_period", question: Q.right_period, verdict: "pass", answer: null },
            ]}
            summary="40 of 40 payments supported"
            secondary={{ label: "Rerun", icon: "rotate-ccw", onClick: noop }}
            provenance={PROVENANCE}
          />
        </Held>
      </Row>
      <Row name="Running" spec="spinner, skeleton answers, footer disabled">
        <Held name="running">
          <ScreeningCard
            verdict="flagged"
            running="Screening 2 new files…"
            request={REQUEST}
            checks={[
              { key: "right_document", question: Q.right_document, verdict: "flag", answer: null },
              { key: "right_period", question: Q.right_period, verdict: "pass", answer: null },
            ]}
            primary={{ label: "Draft follow-up", onClick: noop }}
            secondary={{ label: "Rerun", icon: "rotate-ccw", onClick: noop }}
          />
        </Held>
      </Row>
      <Row name="Not screened" spec="ring, one line, Screen now held off">
        <Held name="not screened">
          <ScreeningCard
            verdict="not_screened"
            checks={[]}
            notScreened="Screening has not run on this file. It runs once the file is linked to a request."
            secondary={{ label: "Screen now", disabled: true }}
            primary={{ label: "Link to request…", opensDialog: true, disabled: true }}
          />
        </Held>
      </Row>
    </Sheet>
  );
}
