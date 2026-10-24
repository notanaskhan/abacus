// SHL-07's artboards (gallery only; P-03-T11): the popover over the Northwind Service Organizations workpaper (AUD-04)
// and, for the guidance variant, AUD-05 Risk Assessment, as the handoff draws them: the cited
// "Keystone Retirement Services" cell lights purple, its row lights, and the popover opens beside
// it. The underlay is the screen's context only (AUD-04 and AUD-05 are A-01's); the container and
// the chips are what P-03 ships. Data only through the generated client.

import { MATCH_ROW, MatchScope, cn } from "@abacus/ui";
import type { JSX } from "react";
import { CitationList } from "./CitationList";
import { CitationPopoverContainer, CitedCell } from "./CitationPopoverContainer";
import { COPY } from "./copy";
import {
  KEYSTONE_CELL,
  OPENS,
  RISK_GUIDANCE_REF,
  RISK_WORKPAPER,
  SERVICE_ORGANIZATIONS,
  SERVICE_ORGS_SECTION,
  SERVICE_ORGS_WORKPAPER,
  type Shl07State,
} from "./scenarios";

const TH = "h-[30px] bg-band-hd px-[10px] text-left text-th font-medium text-ink-2 hairline-b";
const TD = "h-[27px] px-[10px] text-cell text-ink hairline-b";

function ServiceOrganizations({ state }: { state: Shl07State }): JSX.Element {
  const host = `workpaper:${SERVICE_ORGS_WORKPAPER}`;
  return (
    <section
      data-screen="SHL-07"
      data-state={state}
      className="flex min-h-0 flex-1 flex-col bg-card"
    >
      <h2 className="flex h-[46px] items-center justify-center text-pane font-medium hairline-b">
        {COPY.workpaper.title}
      </h2>
      <p className="flex h-[30px] items-center bg-espresso px-[14px] text-cell font-medium tracking-[.04em] text-card uppercase">
        {COPY.workpaper.band}
      </p>
      <p className="px-[14px] pt-[9px] pb-[10px] text-meta text-ink-2 italic hairline-b">
        {COPY.workpaper.caption}
      </p>
      <dl className="grid grid-cols-[118px_1fr] gap-x-[10px] gap-y-[6px] px-[14px] py-[10px] text-meta leading-[1.5]">
        <dt className="font-medium">{COPY.workpaper.procedureKey}</dt>
        <dd>{COPY.workpaper.procedure}</dd>
        <dt className="font-medium">{COPY.workpaper.resultKey}</dt>
        <dd>{COPY.workpaper.result}</dd>
      </dl>
      <table className="w-full border-collapse">
        <thead>
          <tr>
            {COPY.workpaper.columns.map((c) => (
              <th key={c} className={TH}>
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {SERVICE_ORGANIZATIONS.map(([name, services, relevant], i) => (
            <tr
              key={name}
              data-cited-row={i === 0 ? "" : undefined}
              className={i === 0 ? MATCH_ROW : undefined}
            >
              {i === 0 ? (
                <CitedCell
                  anchor={{ type: "workpaper", id: SERVICE_ORGS_WORKPAPER, ref: KEYSTONE_CELL }}
                  openOnMount={OPENS[state].interact}
                  className={TD}
                >
                  {name}
                </CitedCell>
              ) : (
                <td className={TD}>{name}</td>
              )}
              <td className={TD}>{services}</td>
              <td className={TD}>{relevant}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <dl className="grid grid-cols-[118px_1fr] gap-x-[10px] px-[14px] py-[10px] text-meta">
        <dt className="font-medium">{COPY.workpaper.requiredKey}</dt>
        <dd>{COPY.workpaper.required}</dd>
      </dl>
      <footer className="mt-auto flex items-center gap-[8px] px-[14px] py-[11px] hairline-t">
        <CitationList kind="citations" hostRef={host} sectionId={SERVICE_ORGS_SECTION} />
        <CitationList kind="procedures" hostRef={host} sectionId={SERVICE_ORGS_SECTION} />
      </footer>
    </section>
  );
}

function RiskGuidance({ state }: { state: Shl07State }): JSX.Element {
  return (
    <section
      data-screen="SHL-07"
      data-state={state}
      className="flex flex-1 flex-col bg-card p-[14px]"
    >
      <CitedCell
        as="button"
        anchor={{ type: "workpaper", id: RISK_WORKPAPER, ref: RISK_GUIDANCE_REF }}
        openOnMount={OPENS[state].interact}
        className={cn("self-start rounded-tile px-[8px] py-[4px] text-section font-medium")}
      >
        {COPY.guidance.title}
      </CitedCell>
    </section>
  );
}

/** One SHL-07 artboard on its scenario. */
export function SHL07({ state }: { state: Shl07State }): JSX.Element {
  const variant = OPENS[state].variant;
  return (
    <MatchScope>
      {variant === "guidance" ? (
        <RiskGuidance state={state} />
      ) : (
        <ServiceOrganizations state={state} />
      )}
      <CitationPopoverContainer variant={variant} />
    </MatchScope>
  );
}
