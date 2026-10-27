# Export-signing keys

The public halves of each environment's audit-log export-signing key (G-02-T17, DEC-621;
`infra/modules/kms-export-signing`). An audit-log export from ADM-07 is a ZIP of
`audit-log-<from>-<to>.csv`, `manifest.json` and `manifest.sig`. To check one:

```
shasum -a 256 audit-log-<from>-<to>.csv        # equals manifest.json files[0].sha256
openssl dgst -sha256 -verify export-signing-<env>.pem -signature manifest.sig manifest.json
```

`manifest.sig` is a DER-encoded ECDSA P-256 signature over SHA-256 of `manifest.json`, made by
AWS KMS (`ECDSA_SHA_256`); `manifest.json` names the key in `signature.key_ref`. A rotated key
gets a new row; an old public key stays here so the bundles it signed can still be checked.

| Environment | Key reference | Published | Public key (PEM) |
|---|---|---|---|
| staging | `alias/abacus/staging/export-signing` | not yet applied | published after the first apply (infra/README.md "Export-signing key") |
| production | `alias/abacus/production/export-signing` | not yet applied | published after the first apply |

Local runs and tests sign with a key derived from the public local master key
(`LocalExportSigner`, `key_ref` `local:<fingerprint>`): it proves nothing outside them.
