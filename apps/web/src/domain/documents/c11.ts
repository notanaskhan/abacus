// C11 read for the document consumers (P-11-T04; docs/contracts/c11-renderer.md; F-06 §5.2): the
// generated-document read mapped onto what the T10 DocumentOnWell header takes (status, watermark,
// who approved and when) and the field-region manifest F-07's FormRendererLayout and FSP-06's
// merge-field hover read. Every value is the server's: the status is computed by C11 (DF-31),
// never derived here from the versions.
import type {
  FieldRegionsOut,
  GeneratedDocumentOut,
  GeneratedVersionOut,
} from "@abacus/api-client";

export type DocumentHeaderStatus = GeneratedDocumentOut["status"];

/** What T10's header and paper take from C11 (DocumentVM's status, watermark, approvedBy). */
export interface DocumentHeader {
  status: DocumentHeaderStatus;
  /** A draft is stamped; a final version never is (ADR-320 §6). */
  watermark: boolean;
  approvedBy?: { name: string; at: string };
  /** The out-of-date overlay ("Out of date · Update from data"). */
  outOfDate: boolean;
  /** The server's allowed actions decide whether Regenerate… draws. */
  canRegenerate: boolean;
}

export function currentVersion(doc: GeneratedDocumentOut): GeneratedVersionOut | undefined {
  return doc.versions.find((v) => v.n === doc.current_version);
}

export function documentHeader(doc: GeneratedDocumentOut): DocumentHeader {
  const current = currentVersion(doc);
  const approval = current?.approval ?? null;
  return {
    status: doc.status,
    watermark: current?.mode === "draft",
    ...(approval === null ? {} : { approvedBy: { name: approval.by, at: approval.at } }),
    outOfDate: doc.out_of_date,
    canRegenerate: doc.allowed_actions.includes("generated_document.regenerate"),
  };
}

/** One field of a rendered page, as a form renderer places it: points, top-left origin. */
export interface FieldPlacement {
  key: string;
  label: string;
  page: number;
  rect: { x0: number; top: number; x1: number; bottom: number };
  value: string;
  matchId: string;
}

export function fieldManifest(fields: FieldRegionsOut): FieldPlacement[] {
  return fields.items.map((f) => {
    const [x0 = 0, top = 0, x1 = 0, bottom = 0] = f.rect_pt;
    return {
      key: f.field_key,
      label: f.label,
      page: f.page,
      rect: { x0, top, x1, bottom },
      value: f.value_text,
      matchId: f.match_id,
    };
  });
}
