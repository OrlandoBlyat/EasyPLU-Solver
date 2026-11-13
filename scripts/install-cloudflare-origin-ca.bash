#!/usr/bin/env bash
set -euo pipefail

if [[ "$EUID" -ne 0 ]]; then
  echo "Run as root: sudo bash scripts/install-cloudflare-origin-ca.bash" >&2
  exit 1
fi

for executable in curl openssl install; do
  command -v "$executable" >/dev/null || {
    echo "Missing required command: $executable" >&2
    exit 1
  }
done

temporary_file="$(mktemp)"
trap 'rm -f -- "$temporary_file"' EXIT

curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
  https://developers.cloudflare.com/ssl/static/origin_ca_rsa_root.pem > "$temporary_file"
curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 \
  https://developers.cloudflare.com/ssl/static/origin_ca_ecc_root.pem >> "$temporary_file"

certificate_count="$(grep -c -- '-----BEGIN CERTIFICATE-----' "$temporary_file" || true)"
if [[ "$certificate_count" -ne 2 ]]; then
  echo "Downloaded Cloudflare Origin CA bundle is incomplete or invalid." >&2
  exit 1
fi
openssl crl2pkcs7 -nocrl -certfile "$temporary_file" |
  openssl pkcs7 -print_certs -noout >/dev/null

install -d -o root -g root -m 0755 /etc/cloudflare
install -o root -g root -m 0644 "$temporary_file" /etc/cloudflare/origin-ca.pem
echo "Cloudflare Origin CA bundle installed at /etc/cloudflare/origin-ca.pem"
