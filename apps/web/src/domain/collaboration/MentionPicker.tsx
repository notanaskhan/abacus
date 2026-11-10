// C-29 MentionPicker (P-05-T10; SHL-18 b, b2, c; SPEC-650 AC-5, AC-6): O1 300 above the caret, a
// combobox listbox with aria-activedescendant. Only engagement members are selectable; a member of
// the firm who is not on the engagement is greyed and aria-disabled with the reason; a walled
// person is never in the list (the server leaves them out, DEC-43). The agent is never a candidate.
import type { MentionCandidatesOut, PersonCandidateOut } from "@abacus/api-client";
import { type JSX, useEffect } from "react";
import { COPY } from "./copy";

export interface PickerEntry {
  kind: "team" | "member";
  key: string;
  person?: PersonCandidateOut;
}

/** The selectable entries for a query: the team entry for a bare "@", then matching members. */
export function pickerEntries(found: MentionCandidatesOut, query: string): PickerEntry[] {
  const q = query.trim().toLowerCase();
  const entries: PickerEntry[] = [];
  if (q === "" && found.team) entries.push({ kind: "team", key: "team" });
  for (const person of found.members) {
    if (q === "" || person.name.toLowerCase().includes(q)) {
      entries.push({ kind: "member", key: person.user_id, person });
    }
  }
  return entries;
}

function Initials({ text, muted }: { text: string; muted?: boolean }): JSX.Element {
  return (
    <span
      aria-hidden
      className={`flex size-[20px] shrink-0 items-center justify-center rounded-pill bg-chip text-[10.5px] font-medium ${muted ? "text-ink-4" : "text-ink-2"}`}
    >
      {text}
    </span>
  );
}

function Highlight({ name, query }: { name: string; query: string }): JSX.Element {
  const i = query ? name.toLowerCase().indexOf(query.toLowerCase()) : -1;
  if (i < 0) return <>{name}</>;
  return (
    <>
      {name.slice(0, i)}
      <span className="font-medium">{name.slice(i, i + query.length)}</span>
      {name.slice(i + query.length)}
    </>
  );
}

export interface MentionPickerProps {
  id: string;
  found: MentionCandidatesOut;
  query: string;
  engagementLabel: string;
  active: number;
  onActive: (index: number) => void;
  onPick: (entry: PickerEntry) => void;
}

export function MentionPicker({
  id,
  found,
  query,
  engagementLabel,
  active,
  onActive,
  onPick,
}: MentionPickerProps): JSX.Element {
  const entries = pickerEntries(found, query);
  const others = query.trim() ? (found.not_on_engagement ?? []) : [];
  useEffect(() => {
    if (active >= entries.length && entries.length > 0) onActive(0);
  }, [active, entries.length, onActive]);
  const restricted = others.length > 0;
  return (
    <div
      data-c29="mention-picker"
      className="w-[300px] rounded-[12px] bg-card p-[4px] shadow-e3"
      role="presentation"
    >
      {entries.length === 0 && query.trim() ? (
        <p className="px-[10px] py-[8px] text-[12.5px] text-ink-2">{COPY.noMatch(query.trim())}</p>
      ) : (
        <p className="px-[10px] pt-[6px] pb-[4px] text-[11px] font-medium text-ink-3">
          {COPY.onEngagement(engagementLabel)}
        </p>
      )}
      <ul id={id} role="listbox" aria-label="Mention someone" className="flex flex-col">
        {entries.map((entry, i) => {
          const selected = i === active;
          const optionId = `${id}-${entry.key}`;
          if (entry.kind === "team" && found.team) {
            return (
              <li
                key={entry.key}
                id={optionId}
                role="option"
                aria-selected={selected}
                className={`flex h-[36px] cursor-default items-center gap-[8px] rounded-[8px] px-[10px] text-[12.5px] ${selected ? "bg-sel-bg" : ""}`}
                onMouseEnter={() => onActive(i)}
                onMouseDown={(e) => {
                  e.preventDefault();
                  onPick(entry);
                }}
              >
                <span className="font-medium">
                  {COPY.teamCount(found.team.label, found.team.member_count)}
                </span>
              </li>
            );
          }
          const person = entry.person as PersonCandidateOut;
          return (
            <li
              key={entry.key}
              id={optionId}
              role="option"
              aria-selected={selected}
              className={`flex h-[36px] cursor-default items-center gap-[8px] rounded-[8px] px-[10px] text-[12.5px] ${selected ? "bg-sel-bg" : ""}`}
              onMouseEnter={() => onActive(i)}
              onMouseDown={(e) => {
                e.preventDefault();
                onPick(entry);
              }}
            >
              <Initials text={person.initials} />
              <span className="truncate">
                <Highlight name={person.name} query={query.trim()} />
                {person.is_self ? ` ${COPY.you}` : ""}
              </span>
              {person.title ? (
                <span className="ml-auto truncate text-[11.5px] text-ink-3">{person.title}</span>
              ) : null}
            </li>
          );
        })}
      </ul>
      {restricted ? (
        <>
          <p className="px-[10px] pt-[8px] pb-[4px] text-[11px] font-medium text-ink-3">
            {COPY.notOnEngagement}
          </p>
          <ul aria-label={COPY.notOnEngagement} className="flex flex-col">
            {others.map((person) => (
              <li
                key={person.user_id}
                aria-disabled="true"
                aria-label={`${person.name}, ${COPY.notOnEngagement}`}
                className="flex h-[36px] items-center gap-[8px] px-[10px] text-[12.5px] text-ink-4"
              >
                <Initials text={person.initials} muted />
                <span className="truncate">
                  {person.name}
                  {person.title ? ` · ${person.title}` : ""}
                </span>
                <span className="ml-auto text-[11px]">{COPY.notOnEngagement}</span>
              </li>
            ))}
          </ul>
        </>
      ) : null}
      <p className="border-t-[0.5px] border-hair px-[10px] pt-[6px] pb-[4px] text-[11px] text-ink-3">
        {restricted ? COPY.restricted : COPY.pickerKeys}
      </p>
    </div>
  );
}
