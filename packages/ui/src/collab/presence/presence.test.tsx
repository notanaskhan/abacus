// F-08-T24 (TASK-8930; F-08 §F; DEC-5932): "Tints follow join order with the viewer excluded, idle
// over 5 minutes renders at 60%, and no presence state ever locks a cell, card or section." Plus
// the TTL, the scripted source's static mode and the banner's words.
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  CardPresence,
  CellPresenceRing,
  IDLE_MS,
  PollingPresenceSource,
  type PresenceHeartbeat,
  PresenceStore,
  RecordPresence,
  ScriptedPresenceSource,
  SectionEditingBanner,
  TTL_MS,
} from ".";

afterEach(cleanup);

const T0 = Date.UTC(2026, 8, 24, 14, 30);
const beat = (
  userId: string,
  name: string,
  at: number,
  over: Partial<PresenceHeartbeat> = {},
): PresenceHeartbeat => ({ userId, name, anchor: null, activity: "viewing", at, ...over });

describe("PresenceStore", () => {
  it("tints follow join order, the viewer excluded, the fifth reusing the first", () => {
    const store = new PresenceStore("cole");
    store.apply(beat("cole", "Cole Hart", T0)); // the viewer: never in their own stack
    for (const [i, who] of ["simone", "hannah", "marcus", "dana", "felix"].entries()) {
      store.apply(beat(who, who, T0 + i));
    }
    const peers = store.peers(T0 + 10);
    expect(peers.map((p) => p.userId)).toEqual(["simone", "hannah", "marcus", "dana", "felix"]);
    expect(peers.map((p) => p.tint)).toEqual([1, 2, 3, 4, 1]);
    // A later heartbeat from an earlier joiner keeps their tint.
    store.apply(beat("simone", "simone", T0 + 20));
    expect(store.peers(T0 + 21)[0]?.tint).toBe(1);
  });

  it("idle over 5 minutes, and gone after the 45 s TTL", () => {
    const store = new PresenceStore("cole");
    store.apply(beat("simone", "Simone Baptiste", T0));
    // Heartbeats keep coming without any change: idle after five minutes.
    for (let t = T0; t <= T0 + IDLE_MS + 15_000; t += 15_000) {
      store.apply(beat("simone", "Simone Baptiste", t));
    }
    expect(store.peers(T0 + IDLE_MS + 15_000)[0]?.idle).toBe(true);
    // A new anchor is activity again.
    store.apply(
      beat("simone", "Simone Baptiste", T0 + IDLE_MS + 20_000, {
        anchor: { kind: "cell", key: "SURL-12" },
      }),
    );
    expect(store.peers(T0 + IDLE_MS + 20_000)[0]?.idle).toBe(false);
    expect(store.peers(T0 + IDLE_MS + 20_000 + TTL_MS + 1)).toEqual([]);
  });

  it("on() reads one anchor", () => {
    const store = new PresenceStore("cole");
    store.apply(
      beat("simone", "Simone Baptiste", T0, { anchor: { kind: "cell", key: "SURL-12" } }),
    );
    store.apply(
      beat("hannah", "Hannah Leclerc", T0, { anchor: { kind: "section", key: "note-5" } }),
    );
    expect(store.on("cell", "SURL-12", T0).map((p) => p.name)).toEqual(["Simone Baptiste"]);
  });
});

describe("markers", () => {
  const simone = {
    userId: "simone",
    name: "Simone Baptiste",
    tint: 2 as const,
    idle: false,
    anchor: { kind: "cell" as const, key: "SURL-12" },
    activity: "editing" as const,
    joinedAt: T0,
    lastSeenAt: T0,
  };

  it("the cell ring wears the person's tint and label; idle renders at 60%", () => {
    const { rerender } = render(
      <CellPresenceRing peer={simone}>
        <input aria-label="SURL-12 amount" defaultValue="68,400" />
      </CellPresenceRing>,
    );
    const ring = document.querySelector<HTMLElement>("[data-presence-cell]");
    expect(ring?.className).toContain("ring-viz-d2");
    expect(screen.getByText("Simone Baptiste").className).toContain("bg-viz-p2");
    rerender(
      <CellPresenceRing peer={{ ...simone, idle: true }}>
        <input aria-label="SURL-12 amount" defaultValue="68,400" />
      </CellPresenceRing>,
    );
    expect(document.querySelector("[data-presence-cell]")?.className).toContain("opacity-60");
  });

  it("no presence state locks a cell, card or section", () => {
    render(
      <>
        <CellPresenceRing peer={simone}>
          <input aria-label="SURL-12 amount" defaultValue="68,400" />
        </CellPresenceRing>
        <SectionEditingBanner
          peer={{ ...simone, anchor: { kind: "section", key: "note-5" } }}
          section="Note 5"
        />
        <textarea aria-label="Note 5" defaultValue="Long-term debt" />
        <CardPresence peers={[simone]} />
        <button type="button">Open BH-FS-430</button>
      </>,
    );
    const cell = screen.getByLabelText<HTMLInputElement>("SURL-12 amount");
    fireEvent.change(cell, { target: { value: "70,000" } });
    expect(cell.value).toBe("70,000");
    expect(cell.disabled || cell.readOnly).toBe(false);
    const note = screen.getByLabelText<HTMLTextAreaElement>("Note 5");
    expect(note.disabled || note.readOnly).toBe(false);
    expect(
      screen.getByRole<HTMLButtonElement>("button", { name: "Open BH-FS-430" }).disabled,
    ).toBe(false);
    expect(screen.getByText("Simone Baptiste is editing Note 5")).toBeTruthy();
    expect(
      document.querySelector("[disabled], [aria-disabled='true'], [readonly], [inert]"),
    ).toBeNull();
  });

  it("the record stack names who is here and where", () => {
    render(<RecordPresence peers={[simone]} where="Note 5" />);
    expect(document.querySelector("[data-presence-record]")?.getAttribute("aria-label")).toBe(
      "Active now · Simone Baptiste · Viewing Note 5",
    );
  });
});

describe("sources", () => {
  it("the scripted source under ?static=1 plays every frame at once", () => {
    const seen: string[] = [];
    const source = new ScriptedPresenceSource(
      [
        { afterMs: 0, events: [{ kind: "beat", beat: beat("simone", "Simone Baptiste", T0) }] },
        { afterMs: 60_000, events: [{ kind: "leave", userId: "simone" }] },
      ],
      { static: true },
    );
    source.subscribe((e) => seen.push(e.kind));
    expect(seen).toEqual(["beat", "leave"]);
  });

  it("the polling source reads every heartbeat interval until stopped", async () => {
    vi.useFakeTimers();
    const read = vi.fn(() => Promise.resolve([beat("simone", "Simone Baptiste", T0)]));
    const stop = new PollingPresenceSource(read, 15_000).subscribe(() => undefined);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(read).toHaveBeenCalledTimes(3);
    stop();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(read).toHaveBeenCalledTimes(3);
    vi.useRealTimers();
  });
});
