// BoardCanvas (F-08-T18; TASK-8844; F-08 §B1; T19b–d, TPL-21b–d; chapter 04 §7.5; INV-1; DEC-5843):
// the board engine on dnd-kit. `DndContext` with a pointer and a keyboard sensor, one
// `SortableContext` per column, a `DragOverlay` ghost (e3, rotated 1.5°) while a dashed slot stays
// behind, the target column's inset 2 px ring and +1 count preview, and non-accepting columns
// dimmed to .5. A drop is an intent (`onMoveIntent`) whose result is the server's: `moved` settles,
// `dispatched` shows the run toast, `guarded` springs the card back in 240 ms with the dark toast
// "… Open sign-off…" whose action calls `onOpenSignOff`, `refused` springs back with the reason.
// No drop path signs off, approves, releases, sends or posts (INV-1). Every card has a "Move to…"
// menu with the same intent, and a live region announces source, target and result (WCAG 2.2
// 2.5.7). `runAgent` is true only when the host allows a run on move.
import {
  DndContext,
  type DragEndEvent,
  DragOverlay,
  type DragStartEvent,
  KeyboardSensor,
  PointerSensor,
  useDroppable,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { type JSX, type ReactNode, useState } from "react";
import { cn } from "../cn";
import { Menu } from "../components/popover";
import { toast } from "../components/toast";
import {
  type BoardCardVM,
  type BoardColumn,
  type MoveIntent,
  type MoveResult,
  SPRING_BACK_MS,
} from "./types";

export interface BoardCanvasProps {
  label: string;
  columns: readonly BoardColumn[];
  cards: readonly BoardCardVM[];
  onMoveIntent: (intent: MoveIntent) => Promise<MoveResult>;
  onOpenSignOff?: (cardId: string) => void;
  /** The host's AI policy (P-49): only `allowed` with `on` ever sends `runAgent: true`. */
  runOnMove?: { allowed: boolean; on: boolean };
  renderCard?: (card: BoardCardVM) => ReactNode;
  /** Specimens: hold a state (b dragging with a target, d the guarded spring-back). */
  forceDrag?: { cardId: string; over: string } | undefined;
}

function Column({
  column,
  cards,
  over,
  dragging,
  renderCard,
  onMove,
  columns,
}: {
  column: BoardColumn;
  cards: readonly BoardCardVM[];
  over: boolean;
  dragging: boolean;
  renderCard: (card: BoardCardVM) => ReactNode;
  onMove: (card: BoardCardVM, to: string) => void;
  columns: readonly BoardColumn[];
}): JSX.Element {
  const { setNodeRef } = useDroppable({
    id: `column:${column.key}`,
    disabled: column.accepts === false,
  });
  const dim = dragging && column.accepts === false;
  return (
    <section
      ref={setNodeRef}
      aria-label={column.label}
      data-board-column={column.key}
      data-dim={dim ? "true" : undefined}
      data-over={over ? "true" : undefined}
      className={cn(
        "flex w-[262px] flex-none flex-col gap-[8px] rounded-[12px] p-[8px]",
        dim && "opacity-50",
        over && "inset-ring-2 inset-ring-ink",
      )}
    >
      <header className="sticky top-0 flex h-[40px] items-center gap-[6px] text-[13px] font-medium text-ink">
        <span className="flex-1">{column.label}</span>
        <span data-count className="tabular-nums text-ink-2">
          {String(over ? column.count + 1 : column.count)}
        </span>
      </header>
      <SortableContext items={cards.map((c) => c.id)} strategy={verticalListSortingStrategy}>
        {cards.map((c) => (
          <Card key={c.id} card={c} renderCard={renderCard} onMove={onMove} columns={columns} />
        ))}
      </SortableContext>
    </section>
  );
}

function Card({
  card,
  renderCard,
  onMove,
  columns,
}: {
  card: BoardCardVM;
  renderCard: (card: BoardCardVM) => ReactNode;
  onMove: (card: BoardCardVM, to: string) => void;
  columns: readonly BoardColumn[];
}): JSX.Element {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: card.id,
  });
  return (
    <div
      ref={setNodeRef}
      data-board-card={card.id}
      style={{
        transform: CSS.Transform.toString(transform),
        transition: transition ?? `transform ${String(SPRING_BACK_MS)}ms`,
      }}
      className={cn(
        "relative rounded-[10px] bg-card p-[10px] shadow-e1",
        isDragging && "border border-dashed border-hair bg-transparent shadow-none",
      )}
      {...attributes}
      {...listeners}
    >
      {renderCard(card)}
      <span className="absolute right-[6px] top-[6px]">
        <Menu
          label={`Move ${card.title} to`}
          trigger={
            <button
              type="button"
              aria-label={`Move to… ${card.title}`}
              className="text-[12px] text-ink-3"
            >
              ···
            </button>
          }
          sections={[
            columns
              .filter((c) => c.key !== card.column)
              .map((c) => ({
                label: c.label,
                disabled: c.accepts === false,
                onSelect: () => {
                  onMove(card, c.key);
                },
              })),
          ]}
        />
      </span>
    </div>
  );
}

export function BoardCanvas({
  label,
  columns,
  cards,
  onMoveIntent,
  onOpenSignOff,
  runOnMove,
  renderCard = (c) => <span className="text-[13px] text-ink">{c.title}</span>,
  forceDrag,
}: BoardCanvasProps): JSX.Element {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );
  const [active, setActive] = useState<string | null>(forceDrag?.cardId ?? null);
  const [overColumn, setOverColumn] = useState<string | null>(forceDrag?.over ?? null);
  const [placed, setPlaced] = useState<Record<string, string>>({});
  const [announce, setAnnounce] = useState("");
  const columnOf = (c: BoardCardVM): string => placed[c.id] ?? c.column;
  const labelOf = (key: string): string => columns.find((c) => c.key === key)?.label ?? key;

  const move = async (card: BoardCardVM, to: string): Promise<void> => {
    const from = columnOf(card);
    if (to === from || columns.find((c) => c.key === to)?.accepts === false) return;
    setPlaced((p) => ({ ...p, [card.id]: to })); // optimistic; the server decides
    const result = await onMoveIntent({
      cardId: card.id,
      toColumn: to,
      expectedVersion: card.version,
      runAgent: runOnMove?.allowed === true && runOnMove.on,
    });
    if (result.kind === "moved" || result.kind === "dispatched") {
      setAnnounce(`${card.title} moved from ${labelOf(from)} to ${labelOf(to)}.`);
      if (result.kind === "dispatched") toast.show({ text: result.text });
      return;
    }
    window.setTimeout(() => {
      setPlaced((p) => Object.fromEntries(Object.entries(p).filter(([id]) => id !== card.id)));
    }, 0);
    setAnnounce(`${card.title} stayed in ${labelOf(from)}: ${result.text}`);
    if (result.kind === "guarded") {
      toast.show({
        text: result.text,
        action: "Open sign-off…",
        onAction: () => onOpenSignOff?.(card.id),
      });
    } else {
      toast.show({ kind: "error", text: result.text });
    }
  };

  const onDragStart = (e: DragStartEvent): void => {
    setActive(String(e.active.id));
    const card = cards.find((c) => c.id === e.active.id);
    if (card) setAnnounce(`Picked up ${card.title} in ${labelOf(columnOf(card))}.`);
  };
  const onDragOver = (id: string | null): void => {
    if (id === null) {
      setOverColumn(null);
      return;
    }
    if (id.startsWith("column:")) {
      setOverColumn(id.slice(7));
      return;
    }
    const card = cards.find((c) => c.id === id);
    setOverColumn(card === undefined ? null : columnOf(card));
  };
  const onDragEnd = (e: DragEndEvent): void => {
    const card = cards.find((c) => c.id === e.active.id);
    const target = overColumn;
    setActive(null);
    setOverColumn(null);
    if (card && target) void move(card, target);
  };
  const activeCard = cards.find((c) => c.id === active);
  return (
    <div
      aria-label={label}
      role="region"
      data-board-canvas=""
      className="flex min-h-0 flex-1 gap-[10px] overflow-x-auto p-[12px]"
    >
      <DndContext
        sensors={sensors}
        onDragStart={onDragStart}
        onDragOver={(e) => {
          onDragOver(e.over === null ? null : String(e.over.id));
        }}
        onDragEnd={onDragEnd}
        onDragCancel={() => {
          setActive(null);
          setOverColumn(null);
        }}
      >
        {columns.map((col) => (
          <Column
            key={col.key}
            column={col}
            cards={cards.filter((c) => columnOf(c) === col.key)}
            over={overColumn === col.key && active !== null}
            dragging={active !== null}
            renderCard={renderCard}
            onMove={(card, to) => void move(card, to)}
            columns={columns}
          />
        ))}
        <DragOverlay>
          {activeCard ? (
            <div
              data-board-ghost=""
              className="rotate-[1.5deg] rounded-[10px] bg-card p-[10px] shadow-e3"
            >
              {renderCard(activeCard)}
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>
      <p aria-live="polite" className="sr-only" data-board-announce="">
        {announce}
      </p>
    </div>
  );
}
