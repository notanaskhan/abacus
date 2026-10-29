#!/usr/bin/env bash
# Fills the staging secrets Terraform created empty (Q-01-T14; infra/README.md "Staging").
# Run by the builder from a laptop session on the staging account (AWS_PROFILE=staging), never by a
# session or CI. Values are generated here and written straight to Secrets Manager through a
# private temporary file; nothing is printed, logged or committed.
#
#   infra/envs/staging/fill-secrets.sh generated   role passwords + DSNs, payload keyring, peppers
#   infra/envs/staging/fill-secrets.sh workos      prompts (hidden) for the WorkOS staging API key
#
# `generated` refuses to overwrite a secret that already has a value (re-running it would strand
# the database passwords); rotate deliberately with the RB-09 runbook instead.
set -euo pipefail
umask 077

REGION="us-east-2"
mode="${1:?usage: fill-secrets.sh generated|workos}"
scratch="$(mktemp -d)"
trap 'rm -rf "$scratch"' EXIT

put() { # put <secret-id> <json-file>
  aws secretsmanager put-secret-value --region "$REGION" --secret-id "$1" \
    --secret-string "file://$2" --output text --query Name >/dev/null
  echo "set $1"
}

has_value() {
  aws secretsmanager get-secret-value --region "$REGION" --secret-id "$1" \
    --query VersionId --output text >/dev/null 2>&1
}

hex() { openssl rand -hex "$1"; }

case "$mode" in
  generated)
    host="$(terraform -chdir="$(dirname "$0")" output -raw db_address)"
    for role in owner app relay identity ops; do
      id="abacus/staging/db/${role}"
      if has_value "$id"; then echo "skip $id (already set)"; continue; fi
      password="$(hex 32)"
      url="postgresql+asyncpg://abacus_${role}:${password}@${host}:5432/abacus?sslmode=verify-full"
      printf '{"password":"%s","url":"%s"}' "$password" "$url" > "$scratch/s.json"
      put "$id" "$scratch/s.json"
    done
    id="abacus/staging/temporal/payload-keyring"
    if has_value "$id"; then echo "skip $id (already set)"; else
      printf '{"staging-v1":"%s"}' "$(hex 32)" > "$scratch/s.json"
      put "$id" "$scratch/s.json"
    fi
    id="abacus/staging/peppers"
    if has_value "$id"; then echo "skip $id (already set)"; else
      printf '{"email_suppression":"%s","tin_fingerprint":"%s","run_record_fingerprint":"%s"}' \
        "$(hex 32)" "$(hex 32)" "$(hex 32)" > "$scratch/s.json"
      put "$id" "$scratch/s.json"
    fi
    ;;
  workos)
    read -r -s -p "WorkOS staging API key (input hidden): " key; echo
    [ -n "$key" ] || { echo "no key entered" >&2; exit 1; }
    python3 -c 'import json,sys; print(json.dumps({"api_key": sys.stdin.read().strip()}))' \
      <<<"$key" > "$scratch/s.json"
    unset key
    put "abacus/staging/workos" "$scratch/s.json"
    ;;
  *)
    echo "usage: fill-secrets.sh generated|workos" >&2
    exit 64
    ;;
esac
