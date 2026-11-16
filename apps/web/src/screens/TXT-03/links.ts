import { to } from "../../routes/to";

// TXT-03's designed links (link-contract rule 1; S47 end pass, TASK-8337): the host route passes
// these to the screen's callbacks.

/** "K-1 package" on a beneficiary row: TXP-12 in 1041 mode. */
export function k1PackageLink(returnId: string): ReturnType<typeof to.TXP12> {
  return to.TXP12({ returnId });
}

/** "Review › Trust Calculation": TXT-02, the DNI the allocation reads. */
export function trustCalculationLink(returnId: string): ReturnType<typeof to.TXT02> {
  return to.TXT02({ returnId });
}
