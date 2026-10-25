// ADM-02b Role templates: the eight templates with their member counts (CategoryList grammar,
// rows 33 with a 20px count pill), the pinned locked Accrued Agent row, and the capability grid
// generated from the permission matrix (G-01 AC5.1–AC5.4). Read-only: "Firms may only make it
// stricter. Hard limits are locked." The agent's row is never a column: it is locked, and selecting
// it says what the agent may never do (AC5.3, INV-1).

import type { RoleTemplatesOut } from "@abacus/api-client";
import { CapabilityMatrix, Count, Icon, SkeletonRows } from "@abacus/ui";
import type { JSX } from "react";
import { ROLE_TEMPLATES } from "../../app-core/roleTemplates.gen";
import { COPY } from "./copy";

export const AGENT_KEY = "accrued_agent";

const LABEL_OF_ROW: Readonly<Record<string, string>> = Object.fromEntries(
  ROLE_TEMPLATES.grid.map((r) => [r.key, r.label]),
);

export interface TemplatesProps {
  data: RoleTemplatesOut | undefined;
  /** The selected template (its column is highlighted), or the agent. */
  selected: string | null;
  onSelect: (key: string) => void;
}

export function Templates({ data, selected, onSelect }: TemplatesProps): JSX.Element {
  if (data === undefined) return <SkeletonRows type="table" />;
  const columns = data.templates.map((t) => ({
    key: t.key,
    label: COPY.templates[t.key].label,
  }));
  const rows = data.grid
    .filter((r) => r.key !== AGENT_KEY && r.locked !== true)
    .map((r) => ({
      key: r.key,
      label: LABEL_OF_ROW[r.key] ?? r.key,
      cells: r.cells,
      conditions: r.conditions ?? {},
    }));
  const agentOn = selected === AGENT_KEY;
  return (
    <div className="flex min-h-0 flex-1">
      <nav
        aria-label={COPY.templateList}
        className="flex w-[360px] flex-none flex-col gap-[2px] p-[8px] hairline-r"
      >
        <ul className="flex flex-col gap-[2px]">
          {data.templates.map((t) => {
            const on = t.key === selected;
            const words = COPY.templates[t.key];
            return (
              <li key={t.key}>
                <button
                  type="button"
                  aria-pressed={on}
                  onClick={() => {
                    onSelect(t.key);
                  }}
                  className={`flex min-h-[33px] w-full items-center gap-[8px] rounded-tile px-[12px] py-[5px] text-left ${on ? "bg-sel-bg" : "hover:bg-nav-fill"}`}
                >
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="text-body text-ink">{words.label}</span>
                    <span className="truncate text-meta text-ink-3">{words.line}</span>
                  </span>
                  <Count value={t.member_count} />
                </button>
              </li>
            );
          })}
        </ul>
        <span className="flex-1" />
        <button
          type="button"
          aria-pressed={agentOn}
          onClick={() => {
            onSelect(AGENT_KEY);
          }}
          className={`flex min-h-[44px] w-full items-center gap-[10px] rounded-tile px-[12px] py-[6px] text-left shadow-e1 ${agentOn ? "bg-sel-bg" : "bg-card"}`}
        >
          <Icon name="bot" size={16} className="flex-none text-ink" />
          <span className="flex min-w-0 flex-1 flex-col">
            <span className="text-body text-ink">{COPY.agent.name}</span>
            <span className="text-meta text-ink-3">{COPY.agent.line}</span>
          </span>
          <Icon name="lock" size={13} label={COPY.agent.locked} className="text-ink-3" />
        </button>
      </nav>
      <div className="flex min-w-0 flex-1 flex-col gap-[10px] p-[12px]">
        {agentOn && (
          <p
            role="status"
            className="rounded-tile bg-nested px-[12px] py-[8px] text-para text-ink"
          >
            {COPY.agent.text}
          </p>
        )}
        <div className="overflow-hidden rounded-nested bg-card shadow-e1">
          <CapabilityMatrix
            label={COPY.grid.label}
            header={COPY.grid.header}
            columns={columns}
            rows={rows}
            highlight={agentOn ? null : selected}
            words={COPY.cells}
          />
        </div>
        <p className="text-meta text-ink-3">{COPY.grid.footer}</p>
      </div>
    </div>
  );
}
