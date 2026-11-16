import { FlagOffState } from "@abacus/ui";
import type { JSX } from "react";
import { COPY } from "./copy";
import { AUD35_SCENARIOS, AUD35_STATE, type Aud35Scenario } from "./scenarios";

// AUD-35 Component auditors (A-09-T22; SPEC-658 F6; handoff AUD-35): the T9 queue and detail,
// a to g in fixture mode. Only people send; Send instructions stays disabled with its reason
// until §5 is complete (a); no deliverable status outside Expected, Received, Reviewed and Late.

function Kv({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="flex h-[35px] items-center justify-between text-[13px]">
      <span className="text-ink-2">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}

export function ComponentAuditors({ st }: { st?: string | undefined }): JSX.Element {
  const scenario: Aud35Scenario = (AUD35_SCENARIOS as readonly string[]).includes(st ?? "")
    ? (st as Aud35Scenario)
    : "a";
  if (scenario === "g") {
    return (
      <div data-screen="AUD-35" data-scenario="g">
        <FlagOffState flag="ff.group_audit" label={COPY.title} />
      </div>
    );
  }
  const s = AUD35_STATE[scenario];
  return (
    <div data-screen="AUD-35" data-scenario={scenario} className="flex bg-shell">
      <section aria-label="Queue" className="w-[300px] p-[8px]">
        <h2 className="text-[14px]">{COPY.bandFull}</h2>
        <div className="p-[8px]">
          <div className="text-[12.5px] font-medium">{COPY.auditor}</div>
          <div className="text-[11px] text-ink-3">{COPY.where}</div>
          <span data-pill>{s.queuePill}</span>
        </div>
        <h2 className="text-[14px]">{COPY.bandGroup}</h2>
        <p className="text-[11.5px] text-ink-3">{COPY.groupNote}</p>
      </section>
      <section aria-label="Detail" className="w-[735px]">
        <h1 className="p-[12px] text-[15px] font-medium">{COPY.detailTitle}</h1>
        {s.makeReference && <div role="status">{COPY.makeReferenceBanner}</div>}
        {COPY.kv.map(([label, value]) => (
          <Kv key={label} label={label} value={value} />
        ))}
        {!s.makeReference && <p className="text-[11.5px] text-ink-3">{COPY.makeReferenceOff}</p>}
        <h2>Competence &amp; independence</h2>
        {COPY.competence.map(([label, value]) => (
          <Kv key={label} label={label} value={value} />
        ))}
        <h2>Instructions letter</h2>
        <ol aria-label="Instructions status">
          {COPY.steps.map((label, i) => (
            <li key={label} aria-current={i === s.step ? "step" : undefined}>
              {label}
              {s.stepDates[i] !== null && (
                <span className="text-[11px] text-ink-3"> {s.stepDates[i]}</span>
              )}
            </li>
          ))}
        </ol>
        <ul>
          {COPY.sections.map((section) => (
            <li key={section}>
              {section}
              {section.startsWith("§5") && (
                <span> {s.sectionFiveDone ? COPY.risksDone : COPY.needsInput}</span>
              )}
            </li>
          ))}
        </ul>
        <p className="text-[11px] text-ink-3">{COPY.provenance}</p>
        <h2>Deliverables</h2>
        <table>
          <thead>
            <tr>
              <th>Deliverable</th>
              <th>Due</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {COPY.deliverables.map(([name, due], i) => (
              <tr key={name}>
                <td>{name}</td>
                <td>{due}</td>
                <td data-deliverable-status={s.deliverables[i]}>
                  {s.statusNote[i] ?? s.deliverables[i]}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {s.questions && (
          <section aria-label="Questions">
            {COPY.questions.map(([who, text]) => (
              <article key={who}>
                <div className="text-[11px] text-ink-3">{who}</div>
                <p>{text}</p>
              </article>
            ))}
          </section>
        )}
        {s.followUp && <article aria-label="Draft follow-up">{COPY.followUp}</article>}
        <footer className="p-[10px]">
          <button
            type="button"
            disabled={!s.sectionFiveDone}
            title={s.sectionFiveDone ? undefined : COPY.sendBlocked}
          >
            {COPY.send}
          </button>
          <button type="button">{COPY.request}</button>
          <button type="button">{COPY.preview}</button>
          <p className="text-[11px] text-ink-3">{COPY.footerNote}</p>
        </footer>
      </section>
    </div>
  );
}
