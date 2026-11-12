// AgentDetail (F-07-T07; handoff T4f / WB-06 · Agents › My Agents; WorkbenchLayout's
// `agent_detail` variant beside the 320 agent list). Header 46: the agent's functional name
// (15/500, left) with the provenance chip ("Published by Accrued" on the nested fill, 12.5 ink-2),
// then Pencil and Archive icon buttons and the dark "▶ Run" at the right. Body: the category tile
// and the agent's one-line purpose with "‹category› · Installed ‹date› by ‹person›", the
// Schedule / Reads / Changes / Asks table (key column 176), and Recent runs with a status disc.
// Every value is the host's (L3): the kit invents no agent, schedule or run. "Run" starts a run
// that waits on people for every change; the kit renders no Approve, Sign off, Release or Send.
import type { JSX } from "react";
import { Button, IconButton } from "../../components/button";
import { Spinner } from "../../components/motion";
import { Icon, type IconName } from "../../icons";

export interface AgentFact {
  label: string;
  value: string;
}

export type AgentRunState = "waiting" | "done" | "failed" | "running";

export interface AgentRecentRun {
  id: string;
  title: string;
  /** "Today 9:00 AM · Waiting on Hannah Leclerc": L3's words (formatActor upstream). */
  meta: string;
  state: AgentRunState;
}

export interface AgentDetailProps {
  name: string;
  provenance?: string | null;
  icon: IconName;
  /** The icon tile's category fill (clay is the category colour, never text). */
  tile?: "espresso" | "clay" | "red";
  purpose: string;
  meta: string;
  facts: readonly AgentFact[];
  runs: readonly AgentRecentRun[];
  locked?: boolean;
  onEdit?: () => void;
  onArchive?: () => void;
  onRun?: () => void;
  onOpenRun?: (id: string) => void;
}

export const AGENT_DETAIL_GEOMETRY = { header: 46, tile: 48, keyColumn: 176, tableMax: 990 };

const TILE = {
  espresso: "bg-espresso text-on-dark",
  clay: "bg-clay text-on-dark",
  red: "bg-red text-on-dark",
} as const;

function RunDisc({ state }: { state: AgentRunState }): JSX.Element {
  switch (state) {
    case "waiting":
      return <Icon name="triangle-alert" size={16} className="text-amber" aria-label="Waiting" />;
    case "failed":
      return <Icon name="circle-x" size={16} className="text-red" aria-label="Failed" />;
    case "running":
      return <Spinner size={14} label="Running" showLabel={false} />;
    default:
      return <Icon name="circle-check" size={16} className="text-green" aria-label="Done" />;
  }
}

export function AgentDetail(props: AgentDetailProps): JSX.Element {
  const { name, provenance, icon, tile = "espresso", purpose, meta, facts, runs } = props;
  const locked = props.locked === true;
  return (
    <section data-kit="AgentDetail" aria-label={name} className="flex min-h-0 flex-1 flex-col">
      <header style={{ height: 46 }} className="flex shrink-0 items-center gap-[8px] px-[16px]">
        <h2 className="truncate text-[15px] font-medium">{name}</h2>
        {provenance ? (
          <span
            data-provenance
            className="flex h-[22px] items-center rounded-pill bg-nested px-[9px] text-[12.5px] text-ink-2"
          >
            {provenance}
          </span>
        ) : null}
        <span className="flex-1" />
        <IconButton icon="pencil" label="Edit agent" disabled={locked} onClick={props.onEdit} />
        <IconButton
          icon="archive"
          label="Archive agent"
          disabled={locked}
          onClick={props.onArchive}
        />
        <Button variant="primary" size="sm" icon="play" disabled={locked} onClick={props.onRun}>
          Run
        </Button>
      </header>
      <div className="flex min-h-0 flex-1 flex-col gap-[16px] overflow-y-auto px-[24px] pt-[18px] pb-[24px]">
        <div className="flex items-start gap-[14px]">
          <span
            aria-hidden="true"
            className={`flex size-[32px] shrink-0 items-center justify-center rounded-[8px] ${TILE[tile]}`}
          >
            <Icon name={icon} size={14} />
          </span>
          <div className="flex min-w-0 flex-col gap-[4px]">
            <p className="text-[13.5px] leading-[1.45]">{purpose}</p>
            <p className="text-[11.5px] text-ink-3">{meta}</p>
          </div>
        </div>
        <dl data-facts className="max-w-[990px] overflow-hidden rounded-[10px] bg-card shadow-e1">
          {facts.map((fact) => (
            <div
              key={fact.label}
              className="grid grid-cols-[176px_1fr] shadow-[inset_0_-0.5px_0_rgba(43,31,23,0.10)] last:shadow-none"
            >
              <dt className="px-[13px] py-[9px] text-[12.5px] text-ink-2 shadow-[inset_-0.5px_0_0_rgba(43,31,23,0.10)]">
                {fact.label}
              </dt>
              <dd className="px-[13px] py-[9px] text-[12.5px]">{fact.value}</dd>
            </div>
          ))}
        </dl>
        {runs.length > 0 ? (
          <div className="flex max-w-[990px] flex-col gap-[6px]">
            <h3 className="text-[13px] font-medium">Recent runs</h3>
            <ul className="overflow-hidden rounded-[10px] bg-card shadow-e1">
              {runs.map((run) => (
                <li
                  key={run.id}
                  className="shadow-[inset_0_-0.5px_0_rgba(43,31,23,0.10)] last:shadow-none"
                >
                  <button
                    type="button"
                    data-run={run.id}
                    data-state={run.state}
                    onClick={() => props.onOpenRun?.(run.id)}
                    className="flex min-h-[50px] w-full items-center gap-[12px] px-[13px] text-left hover:bg-sel-bg"
                  >
                    <RunDisc state={run.state} />
                    <span className="flex min-w-0 flex-col">
                      <span className="truncate text-[13px]">{run.title}</span>
                      <span className="truncate text-[11.5px] text-ink-3">{run.meta}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </section>
  );
}
