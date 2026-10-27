// G-01-T16 (DEC-457): `?screen=&st=` serves a built screen's own scenario on the firm entry, and
// a state's opening search is applied only when the URL has none of its own.
import { describe, expect, it } from "vitest";
import { scenarios as adm02 } from "./scenarios/ADM-02";
import { OPENS as ADM03_OPENS, scenarios as adm03 } from "./scenarios/ADM-03";
import { SCREEN_SCENARIOS, screenScenario, withOpens } from "./screen-scenarios";

describe("screen scenarios on the firm entry", () => {
  it("picks the named screen's state, a when no state is named", () => {
    expect(screenScenario("?screen=ADM-03&st=b")?.scenario).toBe(adm03.b);
    expect(screenScenario("?screen=ADM-03&st=b")?.opens).toBe(ADM03_OPENS.b);
    expect(screenScenario("?screen=ADM-02")?.scenario).toBe(adm02.a);
  });

  it("answers null for no screen, an unknown screen or an unknown state", () => {
    expect(screenScenario("?as=grace-holloway")).toBeNull();
    expect(screenScenario("?screen=SHL-99")).toBeNull();
    expect(screenScenario("?screen=ADM-03&st=z")).toBeNull();
  });

  it("registers the built firm-settings screens", () => {
    expect(Object.keys(SCREEN_SCENARIOS)).toEqual([
      "ADM-01",
      "ADM-02",
      "ADM-03",
      "ADM-06",
      "ADM-07",
    ]);
  });

  it("applies the opening search and anchor when the URL names only fixture params", () => {
    expect(
      withOpens(
        "/settings/offices",
        "?screen=ADM-03&st=d&as=grace-holloway",
        "",
        "?expand=CHI#offshore",
      ),
    ).toBe("/settings/offices?expand=CHI&screen=ADM-03&st=d&as=grace-holloway#offshore");
  });

  it("keeps the URL as it is when it carries its own search or the state opens with none", () => {
    const own = "?screen=ADM-03&st=a&expand=DEN";
    expect(withOpens("/settings/offices", own, "", "?expand=CHI")).toBe(`/settings/offices${own}`);
    expect(withOpens("/", "?screen=ADM-02&st=a", "", "")).toBe("/?screen=ADM-02&st=a");
  });
});
