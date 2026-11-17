import { Button, FlagOffState, RadioGroup, Segmented, Tag, Tooltip } from "@abacus/ui";
import { type JSX, useState } from "react";
import { COMPONENTS, COPY, type ComponentRow } from "./copy";
import { AUD34_SCENARIOS, AUD34_STATE, type Aud34Scenario } from "./scenarios";

// AUD-34 Group scoping & component materiality (A-09-T31; SPEC-658 F5; handoff AUD-34) in fixture
// mode, a to f. The decision card is SHL-11's grammar: reserved to the engagement partner, a
// rationale required before Decide, and the agent's recommendation only a tag (it never decides).
// The manager's view disables every radio under the banner (b); no component PM is at or above
// group PM, Operating Co. has none, and coverage reads 78% (never 83%).

type Segment = (typeof COPY.segments)[number];

function Tally({ label, value, amber }: { label: string; value: string; amber?: boolean }) {
  return (
    <div className="flex flex-col gap-[2px] px-[14px]" data-tally={label}>
      <span className="text-[10.5px] tracking-[0.04em] text-ink-3">{label}</span>
      <span className={`text-[14px] font-medium ${amber === true ? "text-warn" : "text-ink"}`}>
        {value}
      </span>
    </div>
  );
}

function DecisionCard({ manager, decided }: { manager: boolean; decided: boolean }): JSX.Element {
  const [choice, setChoice] = useState<string>("pbt_5");
  const [reason, setReason] = useState("");
  if (decided) {
    return (
      <section
        data-aud34="decision"
        data-decided="true"
        className="rounded-card bg-card shadow-e1"
      >
        <p className="flex h-[40px] items-center px-[14px] text-[13px] font-medium text-ok">
          {COPY.decidedLine}
        </p>
        <p className="px-[14px] pb-[10px] text-[12.5px] text-ink-2">{COPY.decidedRationale}</p>
      </section>
    );
  }
  return (
    <section data-aud34="decision" className="rounded-card bg-card shadow-e2">
      <header className="flex h-[40px] items-center gap-[8px] border-b border-hair px-[14px]">
        <span className="flex size-[19px] items-center justify-center rounded-full bg-wash text-[11px]">
          ?
        </span>
        <h2 className="flex-1 text-[14px] font-medium">{COPY.question}</h2>
        <span className="text-[11.5px] text-ink-3">{COPY.reserved}</span>
      </header>
      {manager && (
        <div
          role="status"
          className="flex h-[32px] items-center bg-warn-tint px-[14px] text-[12.5px] text-warn"
        >
          {COPY.managerBanner}
        </div>
      )}
      <div className="px-[14px] py-[9px]">
        <RadioGroup
          label={COPY.question}
          value={choice}
          onChange={setChoice}
          options={COPY.options.map((o) => ({
            value: o.key,
            label: o.label,
            disabled: manager,
            detail: (
              <span className="flex flex-col gap-[2px]">
                {o.tag !== null && <Tag>{o.tag}</Tag>}
                <span className="text-[12.5px] text-ink-2">{o.note}</span>
              </span>
            ),
          }))}
        />
        {!manager && (
          <textarea
            aria-label={COPY.reasonPlaceholder}
            placeholder={COPY.reasonPlaceholder}
            value={reason}
            onChange={(e) => {
              setReason(e.target.value);
            }}
            className="mt-[8px] h-[64px] w-full rounded-[10px] bg-wash p-[8px] text-[12.5px]"
          />
        )}
        <div className="mt-[8px] flex flex-wrap gap-[6px]">
          {COPY.citations.map((c) => (
            <span
              key={c}
              data-citation
              className="h-[22px] rounded-full bg-wash px-[8px] text-[11.5px] leading-[22px]"
            >
              {c}
            </span>
          ))}
        </div>
      </div>
      <footer className="flex items-center justify-between border-t border-hair px-[14px] py-[10px]">
        {manager ? (
          <Button variant="secondary">{COPY.remind}</Button>
        ) : (
          <>
            <Button variant="secondary">{COPY.requestAnalysis}</Button>
            <Button variant="primary" disabled={reason.trim() === ""}>
              {COPY.decide}
            </Button>
          </>
        )}
      </footer>
    </section>
  );
}

function PlannedCell({ row, picking }: { row: ComponentRow; picking: boolean }): JSX.Element {
  return (
    <span className="flex flex-col gap-[2px]">
      <Tag>{COPY.plannedWork[row.planned]}</Tag>
      {row.areas !== null && <span className="text-[11.5px] text-ink-3">{row.areas}</span>}
      {picking && (
        <span data-aud34="suggestion" className="text-[11.5px] text-ink-2">
          {COPY.suggestion}
        </span>
      )}
    </span>
  );
}

function Components({ decided, picking }: { decided: boolean; picking: boolean }): JSX.Element {
  return (
    <section data-aud34="components" className="rounded-card bg-card shadow-e1">
      <header className="flex h-[32px] items-center justify-between px-[14px]">
        <h2 className="text-[13px] font-medium">{COPY.componentsHead}</h2>
        <span className="text-[11.5px] text-ink-3">{COPY.proposedBy}</span>
      </header>
      <table className="w-full text-[12.5px]">
        <thead>
          <tr className="h-[28px] bg-wash-2 text-left text-[11.5px] text-ink-2">
            {COPY.columns.map((c) => (
              <th key={c} className="px-[8px] font-normal">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {COMPONENTS.map((r) => (
            <tr key={r.name} className="h-[40px] border-t border-hair" data-component={r.name}>
              <td className="px-[8px]">
                <span className="flex flex-col">
                  <span>{r.name}</span>
                  <span className="text-[11.5px] text-ink-3">{r.where}</span>
                </span>
              </td>
              <td className="px-[8px] tabular-nums">{r.level}</td>
              <td className="px-[8px]">
                <PlannedCell row={r} picking={picking && r.name === "H&P Real Estate, LLC"} />
              </td>
              <td className="px-[8px]">
                {r.performedBy}
                {r.componentAuditor && <Tag className="ml-[6px]">{COPY.componentAuditorTag}</Tag>}
              </td>
              <td className="px-[8px] text-right tabular-nums">{r.sales}</td>
              <td className="px-[8px] text-right tabular-nums">{r.assets}</td>
              <td
                className={`px-[8px] text-right tabular-nums ${decided ? "text-ink" : "text-ink-2"}`}
                data-pm={r.pm}
              >
                {decided || r.pm === "—" ? (
                  r.pm
                ) : (
                  <Tooltip content={COPY.pendingTip}>
                    <span>{r.pm}</span>
                  </Tooltip>
                )}
              </td>
              <td className="px-[8px] text-right tabular-nums">{r.ofGroup}</td>
            </tr>
          ))}
          <tr className="h-[40px] border-t border-hair font-medium">
            <td className="px-[8px]">{COPY.total}</td>
            <td />
            <td />
            <td />
            <td className="px-[8px] text-right tabular-nums">100%</td>
            <td className="px-[8px] text-right tabular-nums">100%</td>
            <td />
            <td />
          </tr>
        </tbody>
      </table>
      {decided && (
        <footer className="flex justify-end border-t border-hair px-[14px] py-[10px]">
          <Button variant="primary">{COPY.draftInstructions}</Button>
        </footer>
      )}
    </section>
  );
}

function Coverage(): JSX.Element {
  return (
    <section data-aud34="coverage" className="rounded-card bg-card shadow-e1">
      <header className="flex h-[32px] items-center px-[14px]">
        <h2 className="text-[13px] font-medium">{COPY.coverageHead}</h2>
      </header>
      <div className="flex flex-col gap-[10px] px-[14px] py-[8px]">
        {COPY.coverage.map((c) => (
          <div key={c.label} className="flex flex-col gap-[4px]" data-coverage={c.label}>
            <span className="text-[12.5px]">{c.label}</span>
            <div className="flex h-[14px] overflow-hidden rounded-[4px] bg-wash">
              <span className="bg-p2" style={{ width: c.full }} />
              {c.specific !== null && <span className="bg-p1" style={{ width: c.specific }} />}
            </div>
            <span className="text-[11.5px] text-ink-3">
              {[c.full, c.specific, c.analytical].filter((x) => x !== null).join(" · ")}
            </span>
          </div>
        ))}
      </div>
      <footer className="h-[28px] border-t border-hair px-[14px] text-[11px] leading-[28px] text-ink-3">
        {COPY.coverageNote}
      </footer>
    </section>
  );
}

function Aggregation(): JSX.Element {
  return (
    <section data-aud34="aggregation" className="rounded-card bg-card shadow-e1">
      <header className="flex h-[32px] items-center px-[14px]">
        <h2 className="text-[13px] font-medium">{COPY.aggregationHead}</h2>
      </header>
      <p className="px-[14px] pb-[12px] text-[12.5px] text-ink-2">{COPY.aggregation}</p>
    </section>
  );
}

export function GroupScoping({ st }: { st?: string | undefined }): JSX.Element {
  const scenario: Aud34Scenario = (AUD34_SCENARIOS as readonly string[]).includes(st ?? "")
    ? (st as Aud34Scenario)
    : "a";
  const [segment, setSegment] = useState<Segment>(
    scenario === "f" ? "Components" : AUD34_STATE[scenario].segment,
  );
  if (scenario === "f") {
    return (
      <div data-screen="AUD-34" data-scenario="f">
        <FlagOffState flag="ff.group_audit" label={COPY.title} />
      </div>
    );
  }
  const s = AUD34_STATE[scenario];
  return (
    <div data-screen="AUD-34" data-scenario={scenario} className="flex flex-col bg-shell">
      <header className="flex h-[46px] items-center gap-[8px] px-[14px]">
        <h1 className="text-[14.5px] font-medium">{COPY.title}</h1>
        <span data-pill className="rounded-full bg-wash px-[8px] text-[11.5px]">
          {s.decided ? COPY.decidedPill : COPY.proposed}
        </span>
        <span className="flex-1" />
        <Button variant="secondary">{COPY.edit}</Button>
        <Button variant="secondary" disabled={!s.decided}>
          {COPY.signOff}
        </Button>
        <Button variant="secondary">{COPY.sourceDocs}</Button>
      </header>
      <div className="flex h-[42px] items-center gap-[12px] px-[14px]">
        <Segmented
          size="small"
          label={COPY.title}
          options={[...COPY.segments]}
          active={segment}
          onChange={(label) => {
            setSegment(label as Segment);
          }}
        />
        <span className="flex-1 text-center text-[12.5px] text-ink-3">{COPY.basis}</span>
        <Button variant="ghost">{COPY.openInExcel}</Button>
      </div>
      <div data-aud34="tallies" className="flex h-[52px] items-center">
        {s.decided ? (
          <>
            <Tally label={COPY.tallies.groupMateriality} value="240,000" />
            <Tally label={COPY.tallies.groupPm} value="180,000" />
            <Tally label={COPY.tallies.ct} value="12,000" />
          </>
        ) : (
          <>
            <Tally label={COPY.tallies.groupMateriality} value={COPY.tallies.pending} amber />
            <Tally label={COPY.tallies.recommended} value="240,000" />
          </>
        )}
        <Tally label={COPY.tallies.salesFull} value="100%" />
        <Tally label={COPY.tallies.assetsFull} value="78%" />
        <Tally label={COPY.tallies.specific} value="22%" />
        <Tally label={COPY.tallies.auditors} value="1" />
      </div>
      <div className="flex flex-col gap-[12px] p-[12px]">
        <DecisionCard manager={s.manager} decided={s.decided} />
        {segment === "Components" && <Components decided={s.decided} picking={s.picking} />}
        {(segment === "Coverage" || segment === "Components") && <Coverage />}
        {(segment === "Aggregation" || segment === "Components") && <Aggregation />}
      </div>
    </div>
  );
}
