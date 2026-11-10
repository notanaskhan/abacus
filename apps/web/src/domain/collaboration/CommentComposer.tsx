// C-29 CommentComposer (P-05-T10; SHL-18 a–c, f): 40h on #EFEEEB, "@" opens the MentionPicker
// above the caret (↑↓ move, Enter mentions, Esc closes), Send posts. Mentions travel as ids; the
// body stays plain text. The team entry mentions the current team at post time (AC-7).
import type { MentionCandidatesOut } from "@abacus/api-client";
import { Icon } from "@abacus/ui";
import { type JSX, type KeyboardEvent, useId, useMemo, useRef, useState } from "react";
import { COPY } from "./copy";
import { activeMention, insertMention } from "./mentions";
import { MentionPicker, type PickerEntry, pickerEntries } from "./MentionPicker";

export interface ComposerSubmit {
  body: string;
  mentionUserIds: string[];
  mentionTeam: boolean;
}

export interface CommentComposerProps {
  candidates: MentionCandidatesOut | undefined;
  engagementLabel: string;
  initialText?: string;
  hint?: string;
  disabled?: boolean;
  onSubmit: (value: ComposerSubmit) => void;
  onQuery?: (query: string | null) => void;
}

export function CommentComposer({
  candidates,
  engagementLabel,
  initialText = "",
  hint = COPY.hint,
  disabled,
  onSubmit,
  onQuery,
}: CommentComposerProps): JSX.Element {
  const listId = useId();
  const ref = useRef<HTMLTextAreaElement>(null);
  const [text, setText] = useState(initialText);
  const [caret, setCaret] = useState(initialText.length);
  const [closed, setClosed] = useState(false);
  const [active, setActive] = useState(0);
  const [mentions, setMentions] = useState<Record<string, string>>({});
  const [team, setTeam] = useState(false);
  const typing = closed ? null : activeMention(text, caret);
  const entries = useMemo(
    () => (typing && candidates ? pickerEntries(candidates, typing.query) : []),
    [typing, candidates],
  );
  const open = typing !== null && candidates !== undefined;

  const update = (value: string, at: number): void => {
    setText(value);
    setCaret(at);
    setClosed(false);
    setActive(0);
    onQuery?.(activeMention(value, at)?.query ?? null);
  };

  const pick = (entry: PickerEntry): void => {
    if (!typing) return;
    if (entry.kind === "team" && candidates?.team) {
      setTeam(true);
      const next = insertMention(text, typing.start, caret, candidates.team.label);
      update(next, next.length);
    } else if (entry.person) {
      setMentions((m) => ({ ...m, [entry.person?.user_id ?? ""]: entry.person?.name ?? "" }));
      const next = insertMention(text, typing.start, caret, entry.person.name);
      update(next, next.length);
    }
    setClosed(true);
    ref.current?.focus();
  };

  const send = (): void => {
    const body = text.trim();
    if (!body || disabled) return;
    const ids = Object.entries(mentions)
      .filter(([, name]) => body.includes(`@${name}`))
      .map(([id]) => id);
    onSubmit({ body, mentionUserIds: ids, mentionTeam: team });
    setText("");
    setMentions({});
    setTeam(false);
  };

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>): void => {
    if (open && entries.length > 0) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActive((i) => (i + 1) % entries.length);
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setActive((i) => (i - 1 + entries.length) % entries.length);
        return;
      }
      if (e.key === "Enter") {
        e.preventDefault();
        const entry = entries[active];
        if (entry) pick(entry);
        return;
      }
    }
    if (open && e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      setClosed(true);
      return;
    }
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  const activeId = open && entries[active] ? `${listId}-${entries[active]?.key}` : undefined;
  return (
    <div data-c29="composer" className="relative flex flex-col gap-[6px]">
      {open && candidates ? (
        <div className="absolute bottom-[48px] left-0 z-10">
          <MentionPicker
            id={listId}
            found={candidates}
            query={typing?.query ?? ""}
            engagementLabel={engagementLabel}
            active={active}
            onActive={setActive}
            onPick={pick}
          />
        </div>
      ) : null}
      <div className="flex min-h-[40px] items-center gap-[8px] rounded-[12px] bg-sunken px-[12px] shadow-[inset_0_0_0_0.5px_var(--color-hair)]">
        <textarea
          ref={ref}
          rows={1}
          role="combobox"
          aria-expanded={open}
          aria-controls={open ? listId : undefined}
          aria-activedescendant={activeId}
          aria-autocomplete="list"
          aria-label="Comment"
          value={text}
          disabled={disabled}
          placeholder={COPY.placeholder}
          className="min-w-0 flex-1 resize-none bg-transparent py-[10px] text-[13px] text-ink outline-none placeholder:text-ink-3"
          onChange={(e) =>
            update(e.target.value, e.target.selectionStart ?? e.target.value.length)
          }
          onSelect={(e) => setCaret(e.currentTarget.selectionStart ?? text.length)}
          onKeyDown={onKey}
        />
        <button
          type="button"
          aria-label={COPY.send}
          disabled={disabled || text.trim() === ""}
          onClick={send}
          className={`flex size-[28px] shrink-0 items-center justify-center rounded-pill text-[14px] ${text.trim() ? "bg-espresso text-on-dark" : "bg-card text-ink-2 shadow-e1"}`}
        >
          <Icon name="arrow-up" size={14} />
        </button>
      </div>
      <p className="text-[11px] text-ink-3">{hint}</p>
    </div>
  );
}
