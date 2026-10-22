// P-01-T07: SHL-04 has a scenario for every artboard (a, b, b′, c, d, e, f, g), the Raj variant
// and the settings menu. Each answers through the generated client as its frame shows, in the
// shape the OpenAPI document gives the C16 routes.
import {
  type NotificationFeedOut,
  listRequestItems,
  notificationFeed,
  notificationPreferences,
  setNotificationPreferences,
} from "@abacus/api-client";
import { client } from "@abacus/api-client/client";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { type Scenario, installFixtureMode } from "../../app-core/fixture-mode";
import { validateResponse } from "../schema-check";
import { getSeed } from "../seed";
import { scenarios } from "./SHL-04";

const seed = getSeed();
const A1 = seed.engagementIds.A1 ?? "";
type Tab = "all" | "approvals" | "mentions" | "client_activity";

let restore: (() => void) | null = null;
let saved: ReturnType<typeof client.getConfig>;
beforeEach(() => {
  saved = client.getConfig();
  client.setConfig({ baseUrl: "http://fixture.test", throwOnError: true });
});
afterEach(() => {
  restore?.();
  restore = null;
  client.setConfig({ baseUrl: saved.baseUrl ?? "", throwOnError: false });
});

async function feed(scenario: Scenario, tab: Tab = "all"): Promise<NotificationFeedOut> {
  restore?.();
  restore = installFixtureMode(scenario);
  const { data } = await notificationFeed({ query: { tab } });
  expect(validateResponse("GET", "/v1/notifications/feed", data)).toEqual([]);
  return data as NotificationFeedOut;
}

describe("SHL-04 scenarios", () => {
  it("cover every artboard letter, the Raj variant and the settings menu", () => {
    expect(Object.keys(scenarios)).toEqual([
      "a",
      "b",
      "bp",
      "b_raj",
      "c",
      "d",
      "e",
      "f",
      "g",
      "settings",
    ]);
  });

  it("a–f stand at Mon Sep 14, 9:41 AM CT as Hannah; g and settings at Thu Oct 1, 11:00 AM", () => {
    for (const key of ["a", "b", "bp", "c", "d", "e", "f"] as const) {
      expect(scenarios[key].clock, key).toBe("2026-09-14T09:41:00-05:00");
      expect(scenarios[key].persona, key).toBe("hannah-leclerc");
    }
    expect(scenarios.g.clock).toBe("2026-10-01T11:00:00-05:00");
    expect(scenarios.settings.clock).toBe("2026-10-01T11:00:00-05:00");
    expect(scenarios.b_raj.persona).toBe("raj-malhotra");
  });

  it("a: 9 rows, 4 unread, Approvals 3 and Mentions 1 (the contract's §8 counts)", async () => {
    const all = await feed(scenarios.a);
    expect(all.items).toHaveLength(9);
    expect(all.unread_count).toBe(4);
    expect(all.counts).toEqual({ approvals: 3, mentions: 1, client_activity: 0 });
    const d = all.items.find((n) => n.inline_actions.includes("accept_document"));
    expect(d?.subject.type).toBe("evidence_version");
    expect(d?.facts).toMatchObject({
      client_display_name: "Harborline Trust Company",
      match_percent: 96,
      item_status: "Uploaded – needs review",
    });
  });

  it("b lists a, b and d; b′ lists nothing; the Raj variant lists 4", async () => {
    expect((await feed(scenarios.b, "approvals")).items).toHaveLength(3);
    const empty = await feed(scenarios.bp, "approvals");
    expect([empty.items.length, empty.counts.approvals]).toEqual([0, 0]);
    expect((await feed(scenarios.b_raj, "approvals")).items).toHaveLength(4);
    expect((await feed(scenarios.a, "mentions")).items).toHaveLength(1);
    expect((await feed(scenarios.a, "client_activity")).items).toHaveLength(2);
  });

  it("c: the receipt, and the Northwind PBC list reads 12 of 24 received", async () => {
    const all = await feed(scenarios.c);
    const receipts = all.items.map((n) => n.facts.receipt).filter((r) => r !== undefined);
    expect(receipts).toEqual(["✓ Accepted by Hannah Leclerc · 9:42 AM"]);
    const received = async (s: Scenario) => {
      restore?.();
      restore = installFixtureMode(s);
      const { data = [] } = await listRequestItems({ path: { engagement_id: A1 } });
      return [data.filter((r) => r.status === "received").length, data.length];
    };
    expect(await received(scenarios.a)).toEqual([11, 24]);
    expect(await received(scenarios.c)).toEqual([12, 24]);
  });

  it("d: all read; e: empty; g: the four R2 rows with 2 unread", async () => {
    expect((await feed(scenarios.d)).unread_count).toBe(0);
    const empty = await feed(scenarios.e);
    expect([empty.items.length, empty.unread_count]).toEqual([0, 0]);
    const g = await feed(scenarios.g);
    expect([g.items.length, g.unread_count]).toEqual([4, 2]);
  });

  it("f: the list never answers", async () => {
    restore = installFixtureMode(scenarios.f);
    const raced = await Promise.race([
      notificationFeed(),
      new Promise((resolve) => {
        setTimeout(() => {
          resolve("pending");
        }, 20);
      }),
    ]);
    expect(raced).toBe("pending");
  });

  it("settings: the four kinds, Mention email on; a change is kept", async () => {
    restore = installFixtureMode(scenarios.settings);
    const before = (await notificationPreferences()).data;
    expect(validateResponse("GET", "/v1/me/notification-preferences", before)).toEqual([]);
    expect(before?.items.map((p) => [p.kind, p.in_app, p.email])).toEqual([
      ["mention", true, true],
      ["todo_assigned", true, true],
      ["template_update_available", true, false],
      ["trigger_run_finished", true, false],
    ]);
    const after = (
      await setNotificationPreferences({
        body: { items: [{ kind: "trigger_run_finished", in_app: true, email: true }] },
      })
    ).data;
    expect(validateResponse("PUT", "/v1/me/notification-preferences", after)).toEqual([]);
    expect(after?.items.find((p) => p.kind === "trigger_run_finished")?.email).toBe(true);
  });
});
