# destruction-role

Q-05-T14 (ADR-179 / OQ-1; DEC-5823). The only principal that may delete an object version of the
evidence bucket and its us-west-2 replica, assumable by the worker task role with a
`destruction_batch` session tag. S3 still refuses any version under retention or legal hold: the
role can never bypass governance, change a hold or a retention date. An assumption without the
tag pages on-call. The landing zone's `scp-evidence-destruction.json` denies DeleteObjectVersion
on evidence buckets to every other principal. Staging proof: `docs/runbooks/RB-100-destruction-role-proof.md`.
