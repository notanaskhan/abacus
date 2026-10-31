// A-03-T22 (TASK-2507; SPEC-580 AC-18): AUD-11's and AUD-31's consumer assertions against the
// sampling stub and C9 v2 (docs/contracts/sampling.md, docs/contracts/ledger-mapping.md). Typed
// with the generated client (a breaking change fails `tsc`) and checked against the OpenAPI
// document at run time. The pytest half is backend/tests/contracts/{sampling,c09_ledger}/.
import type {
  AccountMappingStateStatus,
  CompletenessTieResultStatus,
  MappingSetStatus,
  SampleSetVersionStatus,
} from "@abacus/api-client";
import { type EnumCovered, STATUS_REGISTRY } from "@abacus/ui";
import { describe, expect, it } from "vitest";
import { validateResponse } from "../schema-check";
import {
  granitePeakMapping,
  granitePeakRun,
  northwindParticipants,
  participantItems,
} from "../seed/sampling";

const versionsCovered: EnumCovered<"sample_set_version", SampleSetVersionStatus> = true;
const tiesCovered: EnumCovered<"completeness_tie_result", CompletenessTieResultStatus> = true;
const mappingCovered: EnumCovered<"mapping_set", MappingSetStatus> = true;
const accountsCovered: EnumCovered<"account_mapping_state", AccountMappingStateStatus> = true;

describe("Sampling and C9 v2 contracts (A-03-T22): types", () => {
  it("covers the four status families", () => {
    expect([versionsCovered, tiesCovered, mappingCovered, accountsCovered]).toEqual([
      true,
      true,
      true,
      true,
    ]);
    expect(Object.keys(STATUS_REGISTRY)).toEqual(
      expect.arrayContaining([
        "sample_set_version",
        "completeness_tie_result",
        "mapping_set",
        "account_mapping_state",
      ]),
    );
  });

  it("matches the OpenAPI document", () => {
    expect(
      validateResponse("get", "/v1/sample-sets/{sample_set_id}", northwindParticipants()),
    ).toEqual([]);
    expect(
      validateResponse("get", "/v1/sample-sets/{sample_set_id}/versions/{version_no}/items", {
        items: participantItems(),
        total: 25,
        next_cursor: null,
        total_capped: false,
        counts: {},
        facets: {},
      }),
    ).toEqual([]);
    expect(
      validateResponse("get", "/v1/engagements/{engagement_id}/mapping-sets", {
        items: [granitePeakMapping()],
        total: 1,
        next_cursor: null,
        total_capped: false,
        counts: {},
        facets: {},
      }),
    ).toEqual([]);
    expect(
      validateResponse("get", "/v1/mapping-sets/{mapping_set_id}/run", granitePeakRun()),
    ).toEqual([]);
  });
});

describe("AUD-11 (Northwind participants, Version 2)", () => {
  const sample = northwindParticipants();

  it("draws 25 of 412 with seed 0x5E2A91 and the first five designed names", () => {
    expect(sample.population.record_count).toBe(412);
    expect(sample.parameters.seed_hex).toBe("0x5E2A91");
    expect(sample.parameters.statistical_crosscheck_size).toBe(22);
    expect(
      participantItems()
        .slice(0, 5)
        .map((i) => i.name),
    ).toEqual([
      "Alicia Brennan",
      "Tomás Ibarra",
      "Priyanka Desai",
      "Gordon Whitfield",
      "Mei Tanaka",
    ]);
  });

  it("ties 13,813,400.00 + 746,600.00 = 14,560,000.00 and strikes Version 1", () => {
    const w3 = sample.population.ties[1];
    expect(w3?.comparisons.map((c) => c.amount)).toEqual(["13813400.00", "746600.00"]);
    expect(sample.population.amount_total).toBe("14560000.00");
    expect(sample.versions.map((v) => [v.version_no, v.status])).toEqual([
      [2, "approved"],
      [1, "superseded"],
    ]);
    expect(sample.versions[1]?.tie_difference).toBe("-182300.00");
  });
});

describe("AUD-31 f (Granite Peak FY2026)", () => {
  it("maps 128 of 128 with TB balanced 1 of 1, prepared by Caleb Dunn", () => {
    const mapping = granitePeakMapping();
    expect([
      mapping.tallies.accounts,
      mapping.tallies.mapped,
      mapping.tallies.need_review,
    ]).toEqual([128, 128, 0]);
    expect([mapping.tallies.tb_balanced, mapping.tallies.tb_count]).toEqual([1, 1]);
    expect(mapping.sign_offs.map((s) => s.initials)).toEqual(["CD"]);
  });
});
