# Fiduciary engine — CPA review packet (T-07-T10)

For the tax CPA's review before M18 (chapter 10 §10.9.3; T-07 §7 professional liability). Due to
the CPA by **Fri Jul 21, 2028**; the send is a person's (Ayush), recorded in the task file when
done. Everything here is synthetic (the Calloway Family Trust, Brightwater Hale).

## What the engine computes
`backend/src/abacus/modules/tax/compute/fiduciary.py` (T-07-T09, DEC-5023): FAI; DNI under
§643(a) with expenses allocated pro rata by character (Treas. Reg. §1.652(b)-3), the qualified
subset and §265; IDD = min(distributions, DNI) less its tax-exempt part (§661(c)); a simple trust
deemed to distribute all FAI (§651); allocation by distribution share (§§652, 662); K-1 (1041)
boxes 1, 2a, 2b and others; retained DNI; the §642(b) exemption; taxable income; the 65-day
window (§663(b)). CCH Axcess stays the engine of record (DEC-77).

## The goldens (`backend/tests/golden/fiduciary/calloway_ty2025.yaml`)

| Case | Screen · state | Key figures |
|---|---|---|
| base | TXT-02 a, TXT-03 a | FAI 430,000 · fees 7,500 / 22,500 · DNI 400,000 (interest 100,000, dividends 300,000, qualified 240,000) · IDD 240,000 · Nora 66.7% 40,000 / 120,000 / 96,000 · Theo 33.3% 20,000 / 60,000 / 48,000 · retained 160,000 · exemption 100 · taxable income 159,900 |
| theo_changed | TXT-02 d | distributions 260,000 · 61.5% / 38.5% · Theo 25,000 / 75,000 / 60,000 · retained 140,000 · taxable income 139,900 |
| principal_invaded | TXT-01 c | 265,000 carried out (Nora 160,000, Theo 105,000) · 135,000 retained |
| by_character | TXT-02 c | interest 100,000 · ordinary dividends 300,000 · qualified 240,000 across Nora, Theo, trust |
| simple_trust | §651 variant | exemption 300 · IDD 400,000 · retained 0 |
| gains_in_dni | AC-6.2 variant | gains 50,000: DNI 450,000 with the clause, 400,000 without (taxable income 209,900) |
| windows | TXT-03 card | TY2025 → Mar 6, 2026 · TY2026 → Mar 6, 2027 · TY2027 → Mar 5, 2028 |

Properties (`test_t07t10_calloway_goldens.py`, Hypothesis): the taxable K-1 boxes foot to IDD for
any distribution set; DNI is conserved (IDD + tax-exempt carried out + retained = DNI); the engine
is idempotent.

## Questions for the CPA
1. Expense allocation: every deductible expense, income- or principal-charged, pro rata across the
   DNI characters (incl. tax-exempt interest, the exempt share non-deductible). Any direct
   allocation the firm prefers?
2. A principal distribution (Art. IV(b)) carries out DNI like any other: agreed for Calloway?
3. Simple trust: deemed distribution of all FAI when less was paid; the excess paid over FAI is
   not carried out for a simple trust in a year without principal invasion. Agreed?
4. The TY2026 and TY2027 §1(e) top bracket thresholds are left blank until the Rev. Proc. is read
   in by a reviewed change. Confirm the source to use.

## Sign-off
- [ ] Reviewed by the tax CPA (name, date) — then set `reviewed_by` in
  `tax/compute/parameters/fiduciary/ty2025.yaml` by a reviewed change.
