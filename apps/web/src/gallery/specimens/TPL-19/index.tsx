import { PortalBrandProvider, SigningCeremony, portalNav } from "@abacus/ui";
import type { JSX } from "react";
import { E6, E6_SIGNERS } from "../../../fixtures/seed/tax";
import type { FixtureParams } from "../../fixture-mode";
import { BRAND, OUTCOME_COPY, e6Envelope } from "../TPL-16";
import { COPY as TPL16_COPY } from "../TPL-16/copy";

// TPL-19 frame 9, mobile sign (F-06-T06; docs/screens/TPL-19.md; F-06 §3 Story 1.6): Mira on the
// Sign tab hands off to the same SigningCeremony at 390 with this specimen's own 72 sticky bar
// (TPL-16g and POR-06 use 64: F-06 §11.2 Q4). The other frames are R-01's and R-03's.
// Registered for /components/screens/TPL-19?st=9.

export const TPL19_STATES = ["9"] as const;

const MIRA = E6_SIGNERS[1] ?? E6_SIGNERS[0];

export function Tpl19Frame9({ frame = false }: { frame?: boolean }): JSX.Element {
  return (
    <PortalBrandProvider brand={BRAND}>
      <SigningCeremony
        envelope={e6Envelope("b")}
        user={MIRA?.name ?? ""}
        backLabel={TPL16_COPY.back}
        completion={{
          title: TPL16_COPY.completedTitle(MIRA?.first ?? ""),
          note: TPL16_COPY.willFile(E6.firm),
        }}
        copy={OUTCOME_COPY}
        layout="phone"
        stickyBarHeight={72}
        nav={portalNav("individual")}
        frame={frame}
        height={844}
      />
    </PortalBrandProvider>
  );
}

export function Tpl19Artboard({ params }: { params: FixtureParams }): JSX.Element {
  return <Tpl19Frame9 frame={params.frame} />;
}
