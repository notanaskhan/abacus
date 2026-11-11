import type {
  CommitteeMemberOut,
  DeliverableRowOut,
  GovernanceLetterOut,
  GovernanceRoomOut,
  RoomInquiryOut,
  RoomLetterRowOut,
} from "@abacus/api-client";
import {
  downloadDeliverable,
  getCommunicationPdf,
  portalAnswer,
  portalQuestionnaire,
  portalSubmit,
} from "@abacus/api-client";
import {
  acknowledgeCommunicationMutation,
  askAuditorMutation,
  getCommunicationOptions,
  listPrivateQuestionsOptions,
  listRoomCommunicationsOptions,
  listRoomInquiriesOptions,
  listRoomReportsOptions,
  listRoomsOptions,
} from "@abacus/api-client/query";
import {
  Button,
  EmptyState,
  Icon,
  PortalBrandProvider,
  PortalLayout,
  RegistryStatus,
  Segmented,
  date as formatDate,
  longDate,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, type ReactNode, useState } from "react";
import { useNow } from "../../app-core/clock";
import { brandOf, governanceNav, useBranding, usePortalToolbar } from "../../domain/portal";
import { COPY } from "./copy";

// POR-15 · Governance room (R-02-T21; docs/screens/POR-15.md; SPEC-646; DEC-93) on T7's reduced
// shell: Communications, Reports and Questions for you, never management's areas. The rail lists the
// room's letters (the server's status words) and the committee with each member's acknowledgement;
// the paper pane is T10's card with the approved letter (no citation markers) and the sticky
// acknowledge bar. Acknowledging sends the `seen_hash` of the letter read with an Idempotency-Key
// (fresh MFA at the server); Ask the auditor… is a private thread on the letter (DV-03). The two
// fraud inquiries are the addressee's own, answered through T-02's questionnaire service and seen
// by the audit team only. A grant that opens no room answers 404: the designed state, never a page.
//
//   a  the planning letter, new, 2 of 3 acknowledged       b  acknowledged by the committee
//   c  Questions for you: two private inquiries           d  the internal control letter (Nov 24)
//   e  Reports: the report and the statements, Download   f  nothing from your auditor yet

export type Tab = "communications" | "reports" | "questions";

export interface Por15Props {
  mobile?: boolean;
  /** Presentation only (the gallery): the 1400 window or the 390 phone. */
  frame?: boolean;
  /** `/governance/$communicationId`: the letter open on arrival. */
  communicationId?: string;
  /** `?tab=`: the reduced nav's area. */
  tab?: Tab;
  onNavigate?: (area: string) => void;
}

const TAB_OF: Readonly<Record<string, Tab>> = {
  [COPY.communications]: "communications",
  [COPY.reports]: "reports",
  [COPY.questions]: "questions",
};
const LABEL_OF: Readonly<Record<Tab, string>> = {
  communications: COPY.communications,
  reports: COPY.reports,
  questions: COPY.questions,
};

function useDay(): (v: string | null | undefined) => string {
  const now = useNow();
  return (v) => (v === null || v === undefined ? "" : formatDate(v, { now }));
}

async function save(blob: Blob, name: string): Promise<void> {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
  await Promise.resolve();
}

function Disc({ done }: { done: boolean }): JSX.Element {
  return (
    <span
      aria-hidden="true"
      data-disc={done ? "done" : "ring"}
      className={`inline-flex size-[15px] shrink-0 items-center justify-center rounded-full ${done ? "bg-green text-on-dark" : "inset-shadow-hair"}`}
    >
      {done && <Icon name="check" size={12} />}
    </span>
  );
}

// --- the rail ---------------------------------------------------------------------------------

function rowSub(row: RoomLetterRowOut, day: (v: string | null | undefined) => string): string {
  if (row.status === "acknowledged" && row.acknowledged_on) {
    return COPY.acknowledgedByCommittee(day(row.acknowledged_on));
  }
  if (row.status === "new" && row.sent_on && row.due_on) {
    return COPY.due(day(row.sent_on), day(row.due_on));
  }
  if (row.sent_on && row.sent_by) return COPY.sentFrom(day(row.sent_on), row.sent_by);
  if (row.sent_on) return COPY.sentOn(day(row.sent_on));
  if (row.due_on) return COPY.expected(day(row.due_on));
  return "";
}

function LetterRow({
  row,
  selected,
  onSelect,
}: {
  row: RoomLetterRowOut;
  selected: boolean;
  onSelect: (id: string) => void;
}): JSX.Element {
  const day = useDay();
  const id = row.id ?? null;
  const sub = rowSub(row, day);
  return (
    <li>
      <button
        type="button"
        data-letter-row={id ?? row.title}
        aria-current={selected ? "true" : undefined}
        disabled={id === null}
        onClick={() => {
          if (id !== null) onSelect(id);
        }}
        className={`flex min-h-[56px] w-full items-center gap-[8px] rounded-nested px-[10px] text-left ${selected ? "bg-sel-bg" : "hover:bg-nested"}`}
      >
        <Disc done={row.status === "acknowledged" || row.status === "sent_acknowledged"} />
        <span className="min-w-0 flex-1">
          <span className="block text-[13px] font-medium">{row.title}</span>
          {sub !== "" && <span className="block text-meta text-ink-3">{sub}</span>}
        </span>
        <RegistryStatus object="governance_room_letter" code={row.status} client />
      </button>
    </li>
  );
}

function Member({ m }: { m: CommitteeMemberOut }): JSX.Element {
  const day = useDay();
  const done = m.acknowledged_on !== null && m.acknowledged_on !== undefined;
  return (
    <li data-member={m.name} className="flex min-h-[34px] items-center gap-[8px] px-[10px]">
      <Disc done={done} />
      <span className="min-w-0 flex-1 text-dense">
        <span className="font-medium">{m.name}</span>{" "}
        <span className="text-ink-3">{m.member_role === "chair" ? COPY.chair : COPY.member}</span>
      </span>
      <span className="text-meta text-ink-3">
        {done ? COPY.acknowledgedOn(day(m.acknowledged_on)) : COPY.notYetAcknowledged}
      </span>
    </li>
  );
}

function Rail({
  room,
  rows,
  committee,
  selected,
  onSelect,
}: {
  room: GovernanceRoomOut;
  rows: readonly RoomLetterRowOut[];
  committee: readonly CommitteeMemberOut[];
  selected: string | null;
  onSelect: (id: string) => void;
}): JSX.Element {
  return (
    <nav aria-label={room.body_name} className="flex flex-col">
      <h2 className="flex h-[46px] items-center justify-center text-[14.5px] font-medium">
        {room.body_name}
      </h2>
      <p className="pb-[8px] text-center text-[12px] text-ink-3">{room.subject}</p>
      <ul>
        {rows.map((r) => (
          <LetterRow
            key={r.id ?? r.title}
            row={r}
            selected={r.id !== null && r.id === selected}
            onSelect={onSelect}
          />
        ))}
      </ul>
      {committee.length > 0 && (
        <section aria-label={COPY.committee}>
          <h3 className="mt-[8px] flex h-[31px] items-center bg-band-hd px-[10px] text-dense font-medium">
            {COPY.committee}
          </h3>
          <ul>
            {committee.map((m) => (
              <Member key={m.name} m={m} />
            ))}
          </ul>
        </section>
      )}
    </nav>
  );
}

// --- the paper --------------------------------------------------------------------------------

/** A section body: paragraphs split by blank lines; lines starting "- " read as a list. */
function Body({ text }: { text: string }): JSX.Element {
  const blocks = text.split("\n\n");
  return (
    <>
      {blocks.map((block) => {
        const lines = block.split("\n");
        if (lines.every((l) => l.startsWith("- "))) {
          return (
            <ul key={block} className="list-disc pl-[18px] text-[12px] leading-[1.55]">
              {lines.map((l) => (
                <li key={l}>{l.slice(2)}</li>
              ))}
            </ul>
          );
        }
        return (
          <p key={block} className="text-[12px] leading-[1.55]">
            {block}
          </p>
        );
      })}
    </>
  );
}

function Paper({ letter, room }: { letter: GovernanceLetterOut; room: GovernanceRoomOut }) {
  const branding = useBranding();
  const firm = branding.data?.firm_name ?? "";
  // The brand's address line may lead with the firm's name ("… LLP · 311 West …"): the letterhead
  // prints the name once, above the address.
  const line = branding.data?.address_line ?? null;
  const address =
    line !== null && firm !== "" && line.startsWith(`${firm} · `)
      ? line.slice(firm.length + 3)
      : line;
  return (
    <article
      data-paper={letter.id}
      className="mx-auto flex w-full max-w-[600px] flex-col gap-[10px] rounded-pane bg-card px-[24px] pt-[20px] pb-[24px] shadow-e2"
    >
      <header className="flex flex-col gap-[2px] pb-[10px] hairline-b">
        <span className="text-[13.5px] font-medium">{firm}</span>
        {address !== null && <span className="text-meta text-ink-3">{address}</span>}
      </header>
      <p className="text-[12px]">{longDate(letter.dated_on)}</p>
      <p className="text-[12px]">{COPY.members(room.body_name, room.subject)}</p>
      {letter.sections.map((s, i) =>
        s.heading === null || s.heading === undefined ? (
          <h3 key={`h-${String(i)}`} className="text-[16px] font-medium">
            {s.body}
          </h3>
        ) : (
          <section key={s.heading} className="flex flex-col gap-[6px]">
            <h4 className="text-[13.5px] font-medium">{s.heading}</h4>
            <Body text={s.body} />
          </section>
        ),
      )}
      <p className="pt-[8px] text-[12px] font-medium">{letter.signed_by}</p>
    </article>
  );
}

function AskAuditor({
  communicationId,
  onClose,
}: {
  communicationId: string;
  onClose: () => void;
}): JSX.Element {
  const [body, setBody] = useState("");
  const queryClient = useQueryClient();
  const ask = useMutation({
    ...askAuditorMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries();
      onClose();
    },
  });
  return (
    <div data-composer="ask-auditor" className="flex flex-col gap-[8px] p-[12px]">
      <textarea
        aria-label={COPY.askAuditor}
        value={body}
        onChange={(e) => {
          setBody(e.target.value);
        }}
        rows={3}
        className="w-full rounded-nested bg-card p-[10px] text-[12.5px] shadow-e1"
      />
      <div className="flex justify-end gap-[8px]">
        <Button size="sm" variant="ghost" onClick={onClose}>
          {COPY.cancel}
        </Button>
        <Button
          size="sm"
          disabled={body.trim() === "" || ask.isPending}
          onClick={() => {
            ask.mutate({
              path: { communication_id: communicationId },
              body: { body },
              headers: { "Idempotency-Key": `${communicationId}:ask:${body}` },
            });
          }}
        >
          {COPY.send}
        </Button>
      </div>
    </div>
  );
}

function PrivateThread({ communicationId }: { communicationId: string }): JSX.Element | null {
  const day = useDay();
  const listed = useQuery({
    ...listPrivateQuestionsOptions({ path: { communication_id: communicationId } }),
    retry: false,
  });
  const items = listed.data?.items ?? [];
  if (items.length === 0) return null;
  return (
    <ol className="mx-auto flex w-full max-w-[600px] flex-col gap-[6px]">
      {items.map((q) => (
        <li
          key={q.id}
          data-private-question={q.id}
          className="rounded-nested bg-card p-[10px] shadow-e1"
        >
          <p className="text-meta text-ink-3">
            {q.author} · {day(q.created_at)}
          </p>
          <p className="whitespace-pre-wrap text-[12.5px]">{q.body}</p>
        </li>
      ))}
    </ol>
  );
}

function LetterPane({
  letter,
  room,
  mobile,
}: {
  letter: GovernanceLetterOut;
  room: GovernanceRoomOut;
  mobile: boolean;
}): JSX.Element {
  const queryClient = useQueryClient();
  const day = useDay();
  const [asking, setAsking] = useState(false);
  const acknowledge = useMutation({
    ...acknowledgeCommunicationMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries();
    },
    onError: () => {
      toast.show(COPY.changed);
      void queryClient.invalidateQueries();
    },
  });
  const canAck = letter.allowed_actions.includes("acknowledge");
  const canAsk = letter.allowed_actions.includes("ask");
  const all = letter.committee.every((m) => m.acknowledged_on);
  const doDownload = async (): Promise<void> => {
    try {
      const { data } = await getCommunicationPdf({
        path: { communication_id: letter.id },
        parseAs: "blob",
        throwOnError: true,
      });
      await save(data, `${letter.title}.pdf`);
    } catch {
      toast.show(COPY.downloadFailed);
    }
  };
  const bar = (canAck || canAsk) && (
    <div
      data-ack-bar
      className={`flex shrink-0 items-center gap-[8px] bg-card px-[16px] hairline-t ${mobile ? "flex-col py-[10px]" : "h-[56px]"}`}
    >
      {!mobile && <p className="flex-1 text-[12.5px] text-ink-2">{COPY.ackLine}</p>}
      {canAsk && !mobile && (
        <Button
          size="sm"
          variant="secondary"
          onClick={() => {
            setAsking(true);
          }}
        >
          {COPY.askAuditor}
        </Button>
      )}
      {canAck && (
        <Button
          size={mobile ? "lg" : "sm"}
          className={mobile ? "w-full" : ""}
          disabled={acknowledge.isPending}
          onClick={() => {
            acknowledge.mutate({
              path: { communication_id: letter.id },
              body: { seen_hash: letter.seen_hash },
              headers: { "Idempotency-Key": `${letter.id}:${letter.seen_hash}` },
            });
          }}
        >
          {COPY.acknowledge}
        </Button>
      )}
    </div>
  );
  return (
    <section aria-label={letter.title} className="flex min-h-0 flex-1 flex-col">
      <header className="flex h-[46px] shrink-0 items-center gap-[10px] px-[12px] hairline-b">
        <span className="w-[120px]" />
        <h2 className="mx-auto flex items-center gap-[8px] text-[14.5px] font-medium">
          {letter.title}
          {letter.status === "acknowledged" && all && (
            <RegistryStatus object="governance_room_letter" code="acknowledged" client />
          )}
        </h2>
        {letter.allowed_actions.includes("download") ? (
          <Button
            size="sm"
            variant="ghost"
            icon="download"
            onClick={() => {
              void doDownload();
            }}
          >
            {COPY.downloadPdf}
          </Button>
        ) : (
          <span className="w-[120px]" />
        )}
      </header>
      <div
        tabIndex={0}
        role="region"
        aria-label="Room"
        className="flex min-h-0 flex-1 flex-col gap-[10px] overflow-y-auto bg-shell p-[14px]"
      >
        <Paper letter={letter} room={room} />
        {letter.status === "acknowledged" && all && (
          <p className="mx-auto text-meta text-ink-3">
            {COPY.acknowledgedByCommittee(
              day(
                letter.committee
                  .map((m) => m.acknowledged_on ?? "")
                  .sort()
                  .at(-1),
              ),
            )}
          </p>
        )}
        <PrivateThread communicationId={letter.id} />
        {asking && (
          <div className="mx-auto w-full max-w-[600px] rounded-pane bg-card shadow-e1">
            <AskAuditor
              communicationId={letter.id}
              onClose={() => {
                setAsking(false);
              }}
            />
          </div>
        )}
      </div>
      {bar}
    </section>
  );
}

// --- Questions for you (c) and Reports (e) ----------------------------------------------------

function Inquiry({
  inquiry,
  value,
  onChange,
}: {
  inquiry: RoomInquiryOut;
  value: string;
  onChange: (v: string) => void;
}): JSX.Element {
  return (
    <article
      data-inquiry={inquiry.question_id}
      className="flex flex-col gap-[10px] rounded-pane bg-card px-[16px] py-[14px] shadow-e1"
    >
      <h3 className="text-[14px] font-medium leading-[1.35]">{inquiry.prompt}</h3>
      <textarea
        aria-label={inquiry.prompt}
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
        }}
        className="h-[96px] w-full rounded-nested bg-nested p-[10px] text-[12.5px]"
      />
    </article>
  );
}

function Questions({ roomId }: { roomId: string }): JSX.Element {
  const branding = useBranding();
  const queryClient = useQueryClient();
  const listed = useQuery({
    ...listRoomInquiriesOptions({ path: { room_id: roomId } }),
    retry: false,
  });
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [sent, setSent] = useState(false);
  const items = listed.data?.items ?? [];
  const ready = items.length > 0 && items.every((i) => (answers[i.question_id] ?? "").trim());
  const send = useMutation({
    mutationFn: async () => {
      // Through T-02's questionnaire service: each answer at the version read, then submit.
      for (const id of [...new Set(items.map((i) => i.questionnaire_id))]) {
        const { data } = await portalQuestionnaire({
          path: { questionnaire_id: id },
          throwOnError: true,
        });
        for (const i of items.filter((x) => x.questionnaire_id === id)) {
          const q = data.questions.find((x) => x.id === i.question_id);
          await portalAnswer({
            path: { questionnaire_id: id, question_id: i.question_id },
            body: { value: answers[i.question_id] ?? "" },
            headers: { "If-Match": q?.answer_version ?? 0 },
            throwOnError: true,
          });
        }
        await portalSubmit({ path: { questionnaire_id: id }, throwOnError: true });
      }
    },
    onSuccess: () => {
      setSent(true);
      void queryClient.invalidateQueries();
    },
    onError: () => {
      toast.show(COPY.changed);
    },
  });
  if (listed.data !== undefined && items.length === 0) {
    return <EmptyState title={COPY.empty} icon="circle-help" />;
  }
  return (
    <section
      tabIndex={0}
      aria-label={COPY.questions}
      className="flex min-h-0 flex-1 flex-col gap-[10px] overflow-y-auto bg-shell p-[14px]"
    >
      {items.map((i) => (
        <Inquiry
          key={i.question_id}
          inquiry={i}
          value={answers[i.question_id] ?? ""}
          onChange={(v) => {
            setAnswers({ ...answers, [i.question_id]: v });
          }}
        />
      ))}
      <p className="text-meta text-ink-3">
        {COPY.privacy(branding.data?.portal_name ?? branding.data?.firm_name ?? "")}
      </p>
      <div>
        {sent ? (
          <p data-answers-sent className="text-[12.5px] text-ink-2">
            {COPY.answersSent}
          </p>
        ) : (
          <Button
            disabled={!ready || send.isPending}
            onClick={() => {
              send.mutate();
            }}
          >
            {COPY.sendAnswers}
          </Button>
        )}
      </div>
    </section>
  );
}

function ReportRow({ row }: { row: DeliverableRowOut }): JSX.Element {
  const day = useDay();
  const download = async (): Promise<void> => {
    if (row.latest_version === null || row.latest_version === undefined) return;
    try {
      const { data } = await downloadDeliverable({
        path: { deliverable_id: row.id, version_no: row.latest_version },
        parseAs: "blob",
        throwOnError: true,
      });
      await save(data, `${row.title}.pdf`);
    } catch {
      toast.show(COPY.downloadFailed);
    }
  };
  const sub = [
    row.page_count === null || row.page_count === undefined ? null : COPY.pages(row.page_count),
    row.released_on === null || row.released_on === undefined ? null : day(row.released_on),
  ]
    .filter((s) => s !== null)
    .join(" · ");
  return (
    <li
      data-report={row.id}
      className="flex min-h-[56px] items-center gap-[10px] px-[16px] hairline-t first:shadow-none"
    >
      <Icon name="file-text" size={15} className="text-ink-3" />
      <span className="min-w-0 flex-1">
        <span className="block text-[13.5px] font-medium">{row.title}</span>
        {sub !== "" && <span className="block text-meta text-ink-3">{sub}</span>}
      </span>
      <RegistryStatus object="deliverable" code={row.status} client />
      <Button
        size="sm"
        variant="secondary"
        icon="download"
        onClick={() => {
          void download();
        }}
      >
        {COPY.download}
      </Button>
    </li>
  );
}

function Reports({ roomId }: { roomId: string }): JSX.Element {
  const listed = useQuery({
    ...listRoomReportsOptions({ path: { room_id: roomId } }),
    retry: false,
  });
  const items = listed.data?.items ?? [];
  if (listed.data !== undefined && items.length === 0) {
    return <EmptyState title={COPY.noReports} icon="file-text" />;
  }
  return (
    <section
      aria-label={COPY.reports}
      className="flex min-h-0 flex-1 flex-col overflow-y-auto bg-shell p-[14px]"
    >
      <ul className="rounded-pane bg-card shadow-e1">
        {items.map((r) => (
          <ReportRow key={r.id} row={r} />
        ))}
      </ul>
    </section>
  );
}

// --- the screen -------------------------------------------------------------------------------

function Room(props: Por15Props): JSX.Element {
  const bar = usePortalToolbar(null);
  const mobile = props.mobile === true;
  const [tab, setTab] = useState<Tab>(props.tab ?? "communications");
  const [chosen, setChosen] = useState<string | null>(props.communicationId ?? null);
  const rooms = useQuery({ ...listRoomsOptions(), retry: false });
  const room = rooms.data?.items[0];
  const letters = useQuery({
    ...listRoomCommunicationsOptions({ path: { room_id: room?.id ?? "" } }),
    enabled: room !== undefined,
    retry: false,
  });
  const rows = letters.data?.items ?? [];
  const selected = chosen ?? rows.find((r) => r.id !== null && r.id !== undefined)?.id ?? null;
  const open = useQuery({
    ...getCommunicationOptions({ path: { communication_id: selected ?? "" } }),
    enabled: selected !== null,
    retry: false,
  });
  const closed = (rooms.data !== undefined && room === undefined) || letters.isError;
  const empty = letters.data !== undefined && rows.every((r) => !r.id);

  let main: ReactNode = null;
  if (closed) {
    main = <EmptyState title={COPY.notOn} icon="landmark" />;
  } else if (room !== undefined && tab === "questions") {
    main = <Questions roomId={room.id} />;
  } else if (room !== undefined && tab === "reports") {
    main = <Reports roomId={room.id} />;
  } else if (empty) {
    main = (
      <EmptyState title={COPY.empty} icon="landmark">
        {COPY.emptyBody}
      </EmptyState>
    );
  } else if (open.data !== undefined && room !== undefined) {
    main = <LetterPane key={open.data.id} letter={open.data} room={room} mobile={mobile} />;
  }

  const nav = governanceNav(room?.questions_for_you ?? 0);
  const segmented = mobile && room !== undefined && (
    <Segmented
      label={room.body_name}
      options={[COPY.communications, COPY.questions]}
      active={LABEL_OF[tab]}
      onChange={(label) => {
        setTab(TAB_OF[label] ?? "communications");
      }}
      className="mx-[12px] my-[8px]"
    />
  );
  return (
    <PortalLayout
      variant={mobile ? "mobile" : "split"}
      user={bar?.user ?? ""}
      nav={nav}
      active={LABEL_OF[tab]}
      frame={props.frame === true}
      onNavigate={(label) => {
        const next = TAB_OF[label];
        if (next !== undefined) setTab(next);
        else props.onNavigate?.(label);
      }}
    >
      <div
        data-screen="POR-15"
        data-tab={tab}
        className={`flex min-h-0 flex-1 gap-[10px] ${mobile ? "flex-col" : ""}`}
      >
        {segmented}
        {room !== undefined && !closed && tab === "communications" && (
          <section
            aria-label={room.body_name}
            className={`${mobile ? "" : "w-[336px] shrink-0"} overflow-y-auto rounded-pane bg-card p-[10px] shadow-e2`}
          >
            <Rail
              room={room}
              rows={rows}
              committee={letters.data?.committee ?? []}
              selected={selected}
              onSelect={setChosen}
            />
          </section>
        )}
        <div className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-pane bg-card shadow-e2">
          {main}
        </div>
      </div>
    </PortalLayout>
  );
}

export function POR15(props: Por15Props = {}): JSX.Element | null {
  const branding = useBranding();
  if (branding.data === undefined) return null;
  return (
    <PortalBrandProvider brand={brandOf(branding.data)}>
      <Room {...props} />
    </PortalBrandProvider>
  );
}
