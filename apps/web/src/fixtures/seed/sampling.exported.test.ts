// A-03-T16 AC-1 (TASK-2719; DEC-1770; F-04.21): fixture mode's AUD-11 and AUD-31 figures against
// the reads exported from `make seed-demo --slice sampling` at AUD-11 f's clock
// (`make fixtures SNAPSHOT=2026-09-24T10:20`; the backend's equivalence test holds the files to
// the database). Every figure §5.4 designs is the same on both sides: counts, totals, seeds,
// sizes, statuses, ties, the items in draw order and the mapping tallies.
//
// Known gaps, pinned so a new one fails (TASK-2719):
// - ids and hashes: fixture mode's stand-ins against the server's (swapped for stand-ins on
//   export, but from other labels);
// - Northwind's Version 1 reads Superseded in fixture mode (AUD-11 a, struck) and Draft in the
//   load: the service supersedes only an earlier *approved* version (A-03 §5.4 AC; DEC-1770);
// - Northwind's picker lists Distributions (DF-05), which the load does not draw yet;
// - a version's tie difference reads "0.00" in fixture mode and null in the load when it ties,
//   and fixture mode leaves the Participants' sample value out (the design shows none);
// - a participant's record key is the census ID in fixture mode and the census row in the load
//   (DEC-1766), and fixture mode leaves the compensation out (the design shows none);
// - a stratum's value is the load's (the design shows none) and its upper bound is exclusive in
//   the load ($50,000.00) where fixture mode writes the design's $49,999.99;
// - the GL population's tie labels and query are the design's words in fixture mode and the
//   code's in the load ("Population = credits to 1010", "No gaps in check numbers");
// - the mapping's method split (122 prior year, 6 number range) is the load's: the design shows
//   none, so fixture mode leaves those tallies null; Caleb's confirm reads the AUD-31 clock
//   (Sep 14, 11:40 AM) in fixture mode and Sep 11, 3:00 PM in the load; the entity is AUD-31's
//   short name in fixture mode (its focus line, "Granite Peak Outdoor Supply · FY2026") and the
//   entity's legal name in the load; the prior year is the predecessor's file in the load
//   (DEC-1769), which AUD-31 words as for a prior engagement.

import type {
  ListPageSampleItemOut,
  ListPageSampleSetSummaryOut,
  MappingSetOut,
  SampleSetOut,
  SampleSetSummaryOut,
  SampleItemOut,
} from "@abacus/api-client";
import { describe, expect, it } from "vitest";
import granitePopulation from "./2026-09-24t1020.granite-disbursements-v1-population.json";
import graniteItems from "./2026-09-24t1020.granite-disbursements-v1-items.json";
import graniteSet from "./2026-09-24t1020.granite-disbursements.json";
import graniteMapping from "./2026-09-24t1020.granite-mapping.json";
import graniteSets from "./2026-09-24t1020.granite-sample-sets.json";
import northwindPopulation from "./2026-09-24t1020.northwind-participants-v2-population.json";
import northwindItems from "./2026-09-24t1020.northwind-participants-v2-items.json";
import northwindSet from "./2026-09-24t1020.northwind-participants.json";
import northwindSets from "./2026-09-24t1020.northwind-sample-sets.json";
import type { ExportedRead } from "./exported";

type PopulationOut = SampleSetOut["population"];
import {
  granitePeakMapping,
  graniteDisbursements,
  graniteSampleSets,
  northwindParticipants,
  northwindSampleSets,
  participantItems,
} from "./sampling";

/** The figures of a sample set the design shows (AUD-11 cards 1-3 and Versions). */
function setFigures(s: SampleSetOut) {
  return {
    title: s.title,
    purpose: s.purpose,
    version_no: s.version_no,
    status: s.status,
    items_total: s.items_total,
    items_amount: s.items_amount,
    versions: s.versions.map((v) => ({
      version_no: v.version_no,
      seed_hex: v.seed_hex,
      final_size: v.final_size,
      record_count: v.record_count,
      tie_result: v.tie_result,
      // pinned: "0.00" in fixture mode, null in the load, wherever the version ties
      tie_difference: v.tie_result === "tie" ? "tie" : v.tie_difference,
    })),
  };
}

function populationFigures(p: PopulationOut) {
  return {
    record_count: p.record_count,
    record_unit: p.record_unit,
    amount_total: p.amount_total,
    sampling_unit: p.sampling_unit,
    source: p.source.kind,
    ties: p.ties.map((t) => ({ result: t.result, difference: t.difference })),
  };
}

const summaryFigures = (rows: SampleSetSummaryOut[]) =>
  rows.map((r) => ({
    title: r.title,
    current_version_no: r.current_version_no,
    status: r.status,
    final_size: r.final_size,
    population_count: r.population_count,
  }));

describe("AUD-11 a: Northwind Participants", () => {
  const fixture = northwindParticipants();
  const loaded = (northwindSet as ExportedRead<SampleSetOut>).body;

  it("has the same set, versions, seeds and sizes (Version 1's status is pinned)", () => {
    const want = setFigures(fixture);
    expect(want.versions.map((v) => v.version_no)).toEqual([2, 1]);
    expect(fixture.versions.find((v) => v.version_no === 1)?.status).toBe("superseded");
    expect(loaded.versions.find((v) => v.version_no === 1)?.status).toBe("draft");
    const got = setFigures(loaded);
    expect([fixture.items_amount, loaded.items_amount]).toEqual([null, "892430.00"]);
    expect({ ...got, items_amount: null }).toEqual({
      ...want,
      versions: [...want.versions].reverse(),
    });
  });

  it("has census v2's 412 participants, $14,560,000.00 and two ties", () => {
    const got = populationFigures((northwindPopulation as ExportedRead<PopulationOut>).body);
    expect(got).toEqual(populationFigures(fixture.population));
    expect(populationFigures(loaded.population)).toEqual(got);
  });

  it("draws the design's 25 in the design's order (keys and amounts pinned)", () => {
    const got = (northwindItems as ExportedRead<ListPageSampleItemOut>).body.items;
    const want = participantItems();
    const view = (r: SampleItemOut) => [r.position, r.name, r.selection_reason];
    expect(got.map(view)).toEqual(want.map(view));
    expect(want.every((r) => r.record_key.startsWith("NW-") && r.amount === null)).toBe(true);
    expect(got.every((r) => r.record_key.startsWith("NWC-") && r.amount !== null)).toBe(true);
  });

  it("lists Participants as the picker does (Distributions pinned)", () => {
    const got = summaryFigures(
      (northwindSets as ExportedRead<ListPageSampleSetSummaryOut>).body.items,
    );
    const want = summaryFigures(northwindSampleSets());
    expect(want.map((r) => r.title)).toEqual(["Participants", "Distributions"]);
    expect(got).toEqual(want.slice(0, 1));
  });
});

describe("AUD-11 f: Granite Peak Disbursements", () => {
  const fixture = graniteDisbursements();
  const loaded = (graniteSet as ExportedRead<SampleSetOut>).body;

  it("has the same set, Version 1, seed 0x7C31B4 and 24 + 16 = 40", () => {
    expect(setFigures(loaded)).toEqual(setFigures(fixture));
    // pinned: each stratum's value (the design shows none) and the upper bound, which the load
    // holds exclusive ($50,000.00) where fixture mode writes the design's $49,999.99
    const view = (strata: SampleSetOut["strata"]) =>
      strata.map((r) => [
        r.position,
        r.min_amount,
        r.test_rule,
        r.random_count,
        r.population_count,
      ]);
    expect(view(loaded.strata)).toEqual(view(fixture.strata));
    expect(fixture.strata.map((r) => [r.max_amount, r.population_amount])).toEqual([
      [null, null],
      ["49999.99", null],
      ["7750.00", null],
    ]);
    expect(loaded.strata.map((r) => r.max_amount)).toEqual([null, "50000.00", "7750.00"]);
  });

  it("has 1,912 payments, $38,640,200.00 and two ties (labels pinned)", () => {
    const got = populationFigures((granitePopulation as ExportedRead<PopulationOut>).body);
    expect(got).toEqual(populationFigures(fixture.population));
    expect(
      (granitePopulation as ExportedRead<PopulationOut>).body.ties.map((t) => t.label),
    ).toEqual(["Population = credits to 1010", "No gaps in check numbers"]);
    expect(fixture.population.ties.map((t) => t.label)).not.toEqual(
      (granitePopulation as ExportedRead<PopulationOut>).body.ties.map((t) => t.label),
    );
  });

  it("draws 24 by threshold then 16 at random, totalling the set's $3,698,700.00", () => {
    const got = (graniteItems as ExportedRead<ListPageSampleItemOut>).body.items;
    expect(got.map((r) => r.position)).toEqual(Array.from({ length: 40 }, (_, i) => i + 1));
    expect(got.map((r) => r.stratum_position)).toEqual([
      ...Array<number>(24).fill(1),
      ...Array<number>(16).fill(2),
    ]);
    const cents = got.reduce((sum, r) => sum + Math.round(Number(r.amount) * 100), 0);
    expect((cents / 100).toFixed(2)).toBe(fixture.items_amount);
  });

  it("lists Disbursements as the picker does", () => {
    const got = summaryFigures(
      (graniteSets as ExportedRead<ListPageSampleSetSummaryOut>).body.items,
    );
    expect(got).toEqual(summaryFigures(graniteSampleSets()));
  });
});

describe("AUD-31 f: Granite Peak's mapping", () => {
  const fixture = granitePeakMapping();
  const loaded = (graniteMapping as ExportedRead<MappingSetOut>).body.summary;

  it("has 128 of 128 mapped, 0 to review, the TB balanced and Caleb's L1", () => {
    const view = (s: typeof fixture) => ({
      period_end: s.period_end,
      grouping_set_label: s.grouping_set_label,
      run_status: s.run_status,
      status: s.status,
      accounts: s.tallies.accounts,
      mapped: s.tallies.mapped,
      need_review: s.tallies.need_review,
      tb_balanced: s.tallies.tb_balanced,
      tb_count: s.tallies.tb_count,
      sign_offs: s.sign_offs.map((o) => [o.level, o.initials, o.name, o.stale]),
    });
    expect(view(loaded)).toEqual(view(fixture));
  });

  it("pins the method split, the confirm time, the entity's name and the prior source", () => {
    expect([fixture.entity_name, loaded.entity_name]).toEqual([
      "Granite Peak Outdoor Supply",
      "Granite Peak Outdoor Supply, Inc.",
    ]);
    expect([fixture.prior_source, loaded.prior_source]).toEqual([
      "prior_engagement",
      "predecessor_file",
    ]);
    expect([fixture.tallies.prior_year_match, fixture.tallies.number_range]).toEqual([null, null]);
    expect([loaded.tallies.prior_year_match, loaded.tallies.number_range]).toEqual([122, 6]);
    expect(fixture.sign_offs[0]?.at).toBe("2026-09-14T16:40:00.000Z");
    expect(loaded.sign_offs[0]?.at).toBe("2026-09-11T20:00:00Z");
  });

  it("has 128 rows, each mapped by rule", () => {
    const rows = (graniteMapping as ExportedRead<MappingSetOut>).body.rows;
    expect(rows).toHaveLength(128);
    expect(rows.every((r) => r.state === "rule" && r.fs_line_id !== null)).toBe(true);
  });
});
