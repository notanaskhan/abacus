import type { ComponentRoomOut, RoomDeliverableOut } from "@abacus/api-client";
import {
  componentRoomAcknowledgeMutation,
  componentRoomAskMutation,
  componentRoomGetInstructionsOptions,
  componentRoomGetRoomOptions,
  componentRoomListQuestionsOptions,
  componentRoomListRoomsOptions,
} from "@abacus/api-client/query";
import {
  Button,
  Dialog,
  EmptyState,
  PortalBrandProvider,
  PortalLayout,
  date as formatDate,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { useNow } from "../../app-core/clock";
import { brandOf, useBranding, usePortalToolbar } from "../../domain/portal";
import { COPY } from "./copy";

// POR-23 · Component auditor room, live (A-09-T32; A-09-T33's read model; DEC-5407) on T7's reduced
// shell: one nav item "Group audit", one centered 720 pane. The room is the person's own
// component only (the server's `scope_only`); every figure and word is the API's or the handoff's.
// Acknowledge goes through a confirm dialog with an Idempotency-Key; uploads and drops open the
// room's file picker (A-09-T33's routes); no agent is named and "Accrued" appears nowhere.

export interface Por23Props {
  mobile?: boolean;
  frame?: boolean;
}

function DeliverableRow({
  d,
  on,
}: {
  d: RoomDeliverableOut;
  on: (v: string) => string;
}): JSX.Element {
  const due = on(d.due_on);
  const sub =
    d.word === "you_uploaded"
      ? COPY.word.you_uploaded(d.uploaded_on === null ? due : on(d.uploaded_on))
      : d.word === "returned"
        ? COPY.word.returned
        : d.word === "overdue"
          ? COPY.word.overdue(due)
          : COPY.word.due(due);
  return (
    <li
      data-por23="deliverable"
      data-word={d.word}
      className="flex min-h-[52px] items-center gap-[10px] border-b border-hair px-[14px]"
    >
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="text-body text-ink">{d.title}</span>
        <span className={`text-meta ${d.word === "overdue" ? "text-danger" : "text-ink-3"}`}>
          {sub}
        </span>
        {d.word === "returned" && d.return_note !== null && (
          <span className="text-meta text-ink-2">{d.return_note}</span>
        )}
      </span>
      {d.word !== "you_uploaded" && <span className="font-medium text-ink">{COPY.upload}</span>}
    </li>
  );
}

function Pane({ room }: { room: ComponentRoomOut }): JSX.Element {
  const queries = useQueryClient();
  const now = useNow();
  const on = (v: string): string => formatDate(v, { now });
  const [asking, setAsking] = useState(false);
  const [question, setQuestion] = useState("");
  const [key] = useState(() => crypto.randomUUID());
  const instructions = useQuery({
    ...componentRoomGetInstructionsOptions({ path: { room_id: room.id } }),
    retry: false,
  });
  const questions = useQuery({
    ...componentRoomListQuestionsOptions({ path: { room_id: room.id } }),
    retry: false,
  });
  const acknowledge = useMutation({
    ...componentRoomAcknowledgeMutation(),
    onSuccess: () => {
      void queries.invalidateQueries({
        queryKey: componentRoomGetRoomOptions({ path: { room_id: room.id } }).queryKey,
      });
    },
  });
  const ask = useMutation({
    ...componentRoomAskMutation(),
    onSuccess: () => {
      setQuestion("");
      void questions.refetch();
    },
  });
  const firm = room.firm_name;
  return (
    <div data-screen="POR-23" className="flex flex-col">
      <h1 className="h-[46px] border-b border-hair text-center text-title font-medium leading-[46px]">
        {COPY.header}
      </h1>
      <section className="flex flex-col gap-[4px] border-b border-hair px-[18px] py-[16px]">
        <p className="text-heading font-medium text-ink">{room.group_name}</p>
        <p className="text-body text-ink-2">{COPY.component(room.component_name)}</p>
        <p className="text-meta text-ink-2">{COPY.intro(firm)}</p>
        <p className="mt-[6px] text-body font-medium text-ink">
          {COPY.progress(room.uploaded, room.expected)}
        </p>
      </section>
      <section aria-label={COPY.instructions}>
        <div className="flex h-[32px] items-center gap-[6px] bg-wash px-[14px] text-meta font-medium text-ink-2">
          <span className="flex-1">{COPY.instructionsTitle}</span>
          {room.acknowledged_on !== null ? (
            <span className="text-ok">{COPY.acknowledged(on(room.acknowledged_on))}</span>
          ) : instructions.data !== undefined ? (
            <span className="text-ink-3">{COPY.sentOn(on(instructions.data.sent_on))}</span>
          ) : null}
        </div>
        <div className="flex flex-col gap-[8px] px-[22px] py-[14px]">
          {(instructions.data?.sections ?? []).map((s) => (
            <div key={s.number} className="flex flex-col gap-[2px]">
              <p className="text-body font-medium text-ink">{`§${String(s.number)} ${s.title}`}</p>
              <p className="whitespace-pre-line text-meta text-ink-2">{s.body}</p>
            </div>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-[8px] px-[14px] py-[12px]">
          {room.acknowledged_on === null && (
            <Button
              variant="primary"
              onClick={() => {
                setAsking(true);
              }}
            >
              {COPY.acknowledge}
            </Button>
          )}
          <Button
            variant="secondary"
            onClick={() => {
              document.getElementById("por23-composer")?.focus();
            }}
          >
            {COPY.ask}
          </Button>
          {room.acknowledged_on === null && (
            <span className="text-meta text-ink-3">{COPY.acknowledgeNote}</span>
          )}
        </div>
      </section>
      <section aria-label={COPY.deliverables(room.uploaded, room.expected)}>
        <div className="flex h-[32px] items-center bg-wash px-[14px] text-meta font-medium text-ink-2">
          {COPY.deliverables(room.uploaded, room.expected)}
        </div>
        <ul>
          {room.deliverables.map((d) => (
            <DeliverableRow key={d.id} d={d} on={on} />
          ))}
        </ul>
      </section>
      <section aria-label={COPY.questions} className="flex flex-col gap-[8px] pb-[16px]">
        <div className="flex h-[32px] items-center bg-wash px-[14px] text-meta font-medium text-ink-2">
          {COPY.questions}
        </div>
        {(questions.data?.items ?? []).length === 0 ? (
          <p className="px-[14px] text-meta text-ink-3">{COPY.noQuestions(firm)}</p>
        ) : (
          <ul className="flex flex-col gap-[8px] px-[14px]">
            {(questions.data?.items ?? []).map((q) => (
              <li key={q.id} className="rounded-card bg-card p-[10px] shadow-e1">
                <p className="text-meta font-medium text-ink">{q.author_name}</p>
                <p className="whitespace-pre-line text-meta text-ink">{q.body}</p>
              </li>
            ))}
          </ul>
        )}
        <form
          className="mx-[14px] flex items-center gap-[8px]"
          onSubmit={(e) => {
            e.preventDefault();
            if (question.trim() === "") return;
            ask.mutate({
              path: { room_id: room.id },
              body: { body: question.trim() },
              headers: { "Idempotency-Key": crypto.randomUUID() },
            });
          }}
        >
          <input
            id="por23-composer"
            aria-label={COPY.composer(firm)}
            placeholder={COPY.composer(firm)}
            value={question}
            onChange={(e) => {
              setQuestion(e.target.value);
            }}
            className="h-[40px] flex-1 rounded-full bg-wash px-[14px] text-body"
          />
        </form>
      </section>
      <Dialog
        open={asking}
        onOpenChange={setAsking}
        title={COPY.confirmTitle(room.component_name)}
        action={
          <Button
            variant="primary"
            onClick={() => {
              acknowledge.mutate(
                { path: { room_id: room.id }, headers: { "Idempotency-Key": key } },
                {
                  onSettled: () => {
                    setAsking(false);
                  },
                  onError: () => {
                    toast.show(COPY.acknowledge);
                  },
                },
              );
            }}
          >
            {COPY.confirm}
          </Button>
        }
      >
        <p className="text-body text-ink-2">{COPY.acknowledgeNote}</p>
      </Dialog>
    </div>
  );
}

function Room(props: Por23Props): JSX.Element {
  const bar = usePortalToolbar(null);
  const rooms = useQuery({ ...componentRoomListRoomsOptions(), retry: false });
  const roomId = rooms.data?.room_ids[0];
  const room = useQuery({
    ...componentRoomGetRoomOptions({ path: { room_id: roomId ?? "" } }),
    enabled: roomId !== undefined,
    retry: false,
  });
  const closed = (rooms.data !== undefined && roomId === undefined) || room.isError;
  return (
    <PortalLayout
      variant={props.mobile === true ? "mobile" : "reduced"}
      user={bar?.user ?? ""}
      nav={[{ label: COPY.nav, icon: "building-2" }]}
      active={COPY.nav}
      frame={props.frame === true}
    >
      <div className="mx-auto flex w-full max-w-[720px] flex-col overflow-y-auto rounded-pane bg-card shadow-e2">
        {closed ? (
          <EmptyState title={COPY.expired} icon="link-2-off">
            {COPY.expiredBody}
          </EmptyState>
        ) : room.data !== undefined ? (
          <Pane room={room.data} />
        ) : null}
      </div>
    </PortalLayout>
  );
}

export function POR23(props: Por23Props = {}): JSX.Element | null {
  const branding = useBranding();
  if (branding.data === undefined) return null;
  return (
    <PortalBrandProvider brand={brandOf(branding.data)}>
      <Room {...props} />
    </PortalBrandProvider>
  );
}
