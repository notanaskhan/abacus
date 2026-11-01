// The product's name in the firm app's own copy (AGENTS: "Accrued" in every firm UI string).
// The client portal never says it (DEC-01, ADR-133, INV-4): `vite build --mode portal` swaps this
// module for `portal-product.ts`, so firm copy that a shared module carries, but the portal never
// renders, ships without the name. Import the name from here; never write it in shared copy.
export const PRODUCT = "Accrued";
