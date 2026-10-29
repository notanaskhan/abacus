import type { JSX } from "react";
import { cn } from "../../cn";
import { Fieldset } from "../../components/fieldset";
import { ValueRow } from "../../components/inputs";
import { Toggle } from "../../components/toggles";
import { useMatch } from "../../tracing/match";
import type { MatchId } from "../../tracing/types";
import type { ClauseVM, KvRowVM, KvSheetVM, StructureVM, VariableVM } from "./types";

// T10's 470 structure pane (F-06-T14; T10 handoff spec): either a KV sheet (a 32 crumb header, 31
// section bands on #FBFBFA, 33 rows: key 13 ink-2 at the left, the value at the right, a linked
// value in ink with an ink-3 "→", an empty one "—" in ink-4), or, for letters and reports, the
// clause toggles (34 rows, Toggle 34 × 20, a 12.5 ink-3 reason) over a Variables fieldset. A row
// a citation points at lights through the scope's MatchProvider (E1).

const ROW = "flex h-[33px] items-center justify-between gap-[12px] px-[12px] hairline-t";

function KvValue({
  row,
  onOpenLink,
}: {
  row: KvRowVM;
  onOpenLink?: (linkId: string) => void;
}): JSX.Element {
  if (row.value === null) {
    return (
      <span className="text-body text-ink-4" aria-label={`${row.key}: none`}>
        —
      </span>
    );
  }
  if (row.linkId !== undefined) {
    const linkId = row.linkId;
    return (
      <button
        type="button"
        onClick={() => onOpenLink?.(linkId)}
        className="inline-flex min-w-0 items-center gap-[4px] truncate text-body text-ink hover:underline"
      >
        <span className="truncate">{row.value}</span>
        <span aria-hidden="true" className="text-ink-3">
          →
        </span>
      </button>
    );
  }
  return (
    <span className="min-w-0 truncate text-right text-body text-ink tabular-nums">
      {row.value}
    </span>
  );
}

function LitRow({ id, children }: { id: MatchId; children: JSX.Element[] }): JSX.Element {
  const { bind } = useMatch(id);
  return (
    <li {...bind} className={cn(ROW, "transition-colors duration-[360ms] data-[lit]:bg-match-bg")}>
      {children}
    </li>
  );
}

function KvRow({
  row,
  onOpenLink,
}: {
  row: KvRowVM;
  onOpenLink?: (linkId: string) => void;
}): JSX.Element {
  const cells = [
    <span key="k" className="flex-none text-body text-ink-2">
      {row.key}
    </span>,
    <KvValue key="v" row={row} {...(onOpenLink === undefined ? {} : { onOpenLink })} />,
  ];
  return row.match === undefined ? (
    <li className={ROW}>{cells}</li>
  ) : (
    <LitRow id={row.match}>{cells}</LitRow>
  );
}

export function KvSheet({
  sheet,
  onOpenLink,
}: {
  sheet: KvSheetVM;
  onOpenLink?: (linkId: string) => void;
}): JSX.Element {
  return (
    <section data-document="kv-sheet" aria-label={sheet.crumb} className="flex flex-col">
      <div className="flex h-[32px] flex-none items-center bg-band-hd px-[12px] text-dense font-medium text-ink-2">
        {sheet.crumb}
      </div>
      {sheet.sections.map((section) => (
        <section key={section.title} aria-label={section.title} className="flex flex-col">
          <h3 className="flex h-[31px] items-center bg-band-hd px-[12px] text-section hairline-t">
            {section.title}
          </h3>
          <ul className="flex flex-col">
            {section.rows.map((row) => (
              <KvRow
                key={row.key}
                row={row}
                {...(onOpenLink === undefined ? {} : { onOpenLink })}
              />
            ))}
          </ul>
        </section>
      ))}
    </section>
  );
}

export function ClauseToggles({
  clauses,
  disabledReason,
  onToggle,
}: {
  clauses: readonly ClauseVM[];
  /** The document is locked or drafting: every toggle is read-only and says why. */
  disabledReason?: string;
  onToggle?: (id: string, on: boolean) => void;
}): JSX.Element {
  return (
    <ul data-document="clauses" className="flex flex-col">
      {clauses.map((clause) => (
        <li
          key={clause.id}
          className="flex min-h-[34px] items-center gap-[10px] px-[12px] py-[6px] hairline-t"
        >
          <Toggle
            label={clause.label}
            checked={clause.on}
            disabled={clause.required === true || disabledReason !== undefined}
            onChange={(on) => onToggle?.(clause.id, on)}
          />
          <span className="flex min-w-0 flex-1 flex-col">
            <span className="text-body text-ink">{clause.label}</span>
            {clause.reason !== undefined && (
              <span className="text-meta text-ink-3">{clause.reason}</span>
            )}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function VariablesFieldset({
  title,
  variables,
  readOnly,
  onVariable,
}: {
  title: string;
  variables: readonly VariableVM[];
  readOnly: boolean;
  onVariable?: (id: string, value: string) => void;
}): JSX.Element {
  return (
    <Fieldset title={title} flush className="mx-[12px] mt-[12px]">
      {variables.map((v) => (
        <ValueRow
          key={v.id}
          kind="text"
          label={v.label}
          value={v.value}
          readOnly={readOnly}
          onChange={(value) => onVariable?.(v.id, value)}
        />
      ))}
    </Fieldset>
  );
}

export interface StructurePaneProps {
  structure: StructureVM;
  variablesTitle: string;
  /** Locked or drafting: clause toggles and variables are read-only, each saying why. */
  readOnlyReason?: string;
  onOpenLink?: (linkId: string) => void;
  onToggleSection?: (id: string, on: boolean) => void;
  onVariable?: (id: string, value: string) => void;
}

/** The pane's body; DocumentOnWell draws it in the 470 pane. */
export function StructurePane({
  structure,
  variablesTitle,
  readOnlyReason,
  onOpenLink,
  onToggleSection,
  onVariable,
}: StructurePaneProps): JSX.Element {
  if (structure.kind === "kv") {
    return (
      <div className="flex flex-col">
        {structure.sheets.map((sheet) => (
          <KvSheet
            key={sheet.crumb}
            sheet={sheet}
            {...(onOpenLink === undefined ? {} : { onOpenLink })}
          />
        ))}
      </div>
    );
  }
  return (
    <div className="flex flex-col pb-[12px]">
      <ClauseToggles
        clauses={structure.clauses}
        {...(readOnlyReason === undefined ? {} : { disabledReason: readOnlyReason })}
        {...(onToggleSection === undefined ? {} : { onToggle: onToggleSection })}
      />
      {structure.variables.length > 0 && (
        <VariablesFieldset
          title={variablesTitle}
          variables={structure.variables}
          readOnly={readOnlyReason !== undefined}
          {...(onVariable === undefined ? {} : { onVariable })}
        />
      )}
    </div>
  );
}
