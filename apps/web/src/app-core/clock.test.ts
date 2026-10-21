// F-04-T03 (F-04.7): the browser clock's source chain and the Central business date.
import { afterEach, describe, expect, it } from "vitest";
import { nowMs, setScenarioClock, setServerNow, todayIso } from "./clock";

afterEach(() => {
  setScenarioClock(null);
  window.history.replaceState(null, "", "/");
});

describe("the browser clock", () => {
  it("a scenario clock wins over ?clock= and the server offset", () => {
    window.history.replaceState(null, "", "/?clock=2026-10-01T09:00:00-05:00");
    setScenarioClock("2026-09-14T09:41:00-05:00");
    expect(nowMs()).toBe(Date.parse("2026-09-14T09:41:00-05:00"));
  });

  it("?clock= applies in dev and test builds", () => {
    window.history.replaceState(null, "", "/?clock=2026-09-14T09:24:00-05:00");
    expect(nowMs()).toBe(Date.parse("2026-09-14T09:24:00-05:00"));
  });

  it("the server's time sets an offset from the device", () => {
    setServerNow(new Date(Date.now() + 3_600_000).toISOString());
    expect(Math.abs(nowMs() - (Date.now() + 3_600_000))).toBeLessThan(1_000);
    setServerNow(new Date(Date.now()).toISOString());
  });

  it("dates fall in Central time, CDT in September and CST in November", () => {
    expect(todayIso(Date.parse("2026-09-15T04:30:00Z"))).toBe("2026-09-14"); // 11:30 PM CDT
    expect(todayIso(Date.parse("2026-11-10T05:30:00Z"))).toBe("2026-11-09"); // 11:30 PM CST
  });
});
