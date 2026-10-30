// ac-test-author: ayushkbhatia (N-01-T27; independent of N-01-T11, ADR-078). The firm inbox seed
// foots to INB-01 a and d, counted here from the threads themselves, not from the screen: 23
// attachments waiting across the 17 threads, 4 threads with no client, and after Grace's two
// filings (W0) 21 waiting.
import { describe, expect, it } from "vitest";
import { inboxThreads } from "../inbox";

// A thread's files are on the message that carries them: a forwarded thread with an empty top
// message carries them on its replies. Waiting means not yet filed, ignored or new (INB-01's rule).
const waiting = (filed: boolean): number =>
  inboxThreads(filed)
    .flatMap((m) => (m.body === "" && (m.replies?.length ?? 0) > 0 ? (m.replies ?? []) : [m]))
    .flatMap((m) => m.attachments)
    .filter((a) => a.state === "wait").length;

describe("N-01-T27: the firm inbox seed foots", () => {
  it("17 threads, 23 waiting, 4 unmatched (INB-01 a)", () => {
    const threads = inboxThreads();
    expect(threads).toHaveLength(17);
    expect(waiting(false)).toBe(23);
    expect(threads.filter((m) => m.client === null)).toHaveLength(4);
  });

  it("after the two filings, 21 waiting and still 4 unmatched (INB-01 d)", () => {
    expect(waiting(true)).toBe(21);
    expect(inboxThreads(true).filter((m) => m.client === null)).toHaveLength(4);
  });
});
