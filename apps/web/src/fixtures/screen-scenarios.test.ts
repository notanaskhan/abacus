// G-01-T16 (DEC-457): `?screen=&st=` serves a built screen's own scenario on the firm entry, and
// a state's opening search is applied only when the URL has none of its own.
import { describe, expect, it } from "vitest";
import { scenarios as adm02 } from "./scenarios/ADM-02";
import { OPENS as ADM03_OPENS, scenarios as adm03 } from "./scenarios/ADM-03";
import { OPENS as BND02_OPENS } from "./scenarios/BND-02";
import { OPENS as SHL14_OPENS } from "./scenarios/SHL-14";
import { SCREEN_SCENARIOS, screenScenario, withIds, withOpens } from "./screen-scenarios";

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

  it("registers the firm-settings screens and the journeys' binder, request and shell screens", () => {
    expect(Object.keys(SCREEN_SCENARIOS)).toEqual([
      "ADM-01",
      "ADM-02",
      "ADM-03",
      "ADM-06",
      "ADM-07",
      "BND-01",
      "BND-02",
      "SHL-03",
      "SHL-04",
      "SHL-14",
    ]);
  });

  it("names the ids a state opens, leaving out the ones it has none for (P-06-T25)", () => {
    expect(screenScenario("?screen=BND-02&st=b")?.ids).toEqual({
      binderId: BND02_OPENS.b.binderId,
      request: BND02_OPENS.b.request,
    });
    expect(screenScenario("?screen=SHL-14&st=a")?.ids).toEqual({
      binderId: SHL14_OPENS.a.binderId,
    });
    expect(screenScenario("?screen=ADM-03&st=b")?.ids).toEqual({});
  });

  it("resolves _key_ path segments and query values, and leaves unknown ones", () => {
    const ids = { binderId: "b1", requestId: "r1" };
    expect(withIds("/binders/_binderId_", ids)).toBe("/binders/b1");
    expect(withIds("/binders/_binderId_?as=kevin-osei", ids)).toBe("/binders/b1?as=kevin-osei");
    expect(withIds("/binders/_binderId_?ov=request%3A_requestId_%3A_binderId_", ids)).toBe(
      "/binders/b1?ov=request%3Ar1%3Ab1",
    );
    expect(withIds("/binders/_binderId_?request=_requestId_&as=x", ids)).toBe(
      "/binders/b1?request=r1&as=x",
    );
    expect(withIds("/binders/_other_", ids)).toBe("/binders/_other_");
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
