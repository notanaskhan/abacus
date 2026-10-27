# kms-export-signing

The environment's audit-log export-signing key (G-02-T17, DEC-621): an asymmetric KMS key
(`ECC_NIST_P256`, `SIGN_VERIFY`) behind `alias/abacus/<environment>/export-signing`. The worker
signs each export's `manifest.json` with `kms:Sign` (`ECDSA_SHA_256`, `MessageType=DIGEST`); the
account administers the key and cannot sign with it. Written, not applied.

After the first apply, the builder publishes the public key (`aws kms get-public-key`, converted to
PEM) in `docs/operations/export-signing-keys.md` and sets `ABACUS_AUDIT_EXPORT_SIGNING_KEY_ALIAS`
from `task_environment` on the worker. Until then an audit export fails `signing_unavailable`.
