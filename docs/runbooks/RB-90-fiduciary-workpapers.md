# RB-90 · Fiduciary workpapers (T-07-T32)

Who: the tax lead on call. Surfaces: TXT-01 to TXT-04, the 1041 K-1 release, the estate
workpapers. Flags: `tax.fiduciary_workpapers`, `tax.fiduciary_k1_release`,
`tax.estate_workpapers` (per firm, default off).

## The reader refuses
`tax.instrument_reader` refuses without the trust's consent or when a clause does not verify. The
preparer reads the instrument by hand on TXT-01; nothing is proposed. Check the consent on the
trust's entity before re-running; never bypass the clause verifier.

## Re-segmentation and reopen
A changed instrument version re-segments its clauses; adopted interpretations on moved clauses go
stale and the computation's signature drops. Reopen the computation (TXT-02), adopt again, sign.

## K-1 supersede and resend
A change after release supersedes the 1041 K-1 packages (DEC-85): the 8879-F envelope is voided
and release relocks. Re-run final approval, have the trustee sign the new 8879-F, release again;
each recipient's grant still reads only its own package. Resend is TXT-03's control after release.

## CCH tie-out differences
The CCH 1041 file bridge never transmits; it raises a tie-out issue per difference. Resolve each
on the return's issues; the bridge re-imports on the next file.

## The estate's shadow label
TXT-04's "Accrued tie-out (shadow)" label marks the code's figures as a shadow of the preparer's
until the CPA sign-off of the T-07 goldens is recorded (M18). Do not remove it before then.

## Roll back
Turn the flag off for the firm (the routes answer 404 after authorising). No data is deleted;
the migrations are expand-only.
