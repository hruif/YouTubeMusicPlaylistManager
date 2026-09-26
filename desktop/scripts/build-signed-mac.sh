#!/bin/bash
# Build a signed (and, when Apple credentials are available, notarized) macOS app locally.
#
#   CERT_DIR=/path/to/certs APPLE_KEYCHAIN_PROFILE=ytmpm-notary scripts/build-signed-mac.sh [--universal]
#
# CERT_DIR must hold the Developer ID Application certificate (developerID_application.cer, DER)
# and its private key (*.key, PEM). They're bundled into a throwaway .p12 inside a throwaway
# keychain for the duration of the build; your login keychain is never modified, and the keychain
# search list is restored on exit, even on failure.
#
# Notarization runs when APPLE_KEYCHAIN_PROFILE names a profile stored with
#   xcrun notarytool store-credentials <name> --apple-id <you@example.com> --team-id <TEAMID>
# (or when APPLE_ID + APPLE_APP_SPECIFIC_PASSWORD + APPLE_TEAM_ID are set). Otherwise it's skipped.
#
# By default this builds just the .app for this Mac's architecture (release/mac-<arch>/), since a
# local toolchain may not link the other slice of the Swift login helper, and a "universal" DMG
# built that way would carry a helper that can't run on the other architecture. Pass --universal
# for the release-style DMG + zip.
#
# electron-builder's own CSC_LINK import is not used: its set-key-partition-list step unlocks the
# temporary keychain with the certificate password instead of the keychain password, and fails.
set -euo pipefail

cd "$(dirname "$0")/.."

: "${CERT_DIR:?Set CERT_DIR to the folder with developerID_application.cer and the .key}"
CER="$CERT_DIR/developerID_application.cer"
KEY="$(ls "$CERT_DIR"/*.key | head -n 1)"
[[ -f "$CER" && -f "$KEY" ]] || { echo "Missing certificate or key in $CERT_DIR" >&2; exit 1; }

WORK="$(mktemp -d)"
KEYCHAIN="$WORK/ytmpm-sign.keychain-db"
P12_PW="$(openssl rand -hex 24)"
KEYCHAIN_PW="$(openssl rand -hex 24)"

# Remember the keychain search list exactly (one entry per array element) to restore it.
ORIGINAL_KEYCHAINS=()
while IFS= read -r line; do
  line="${line#"${line%%[![:space:]]*}"}"
  line="${line%\"}"
  ORIGINAL_KEYCHAINS+=("${line#\"}")
done < <(security list-keychains -d user)

cleanup() {
  security list-keychains -d user -s "${ORIGINAL_KEYCHAINS[@]}"
  security delete-keychain "$KEYCHAIN" 2>/dev/null || true
  rm -rf "$WORK"
}
trap cleanup EXIT

openssl x509 -inform DER -in "$CER" -out "$WORK/cert.pem"
IDENTITY="$(openssl x509 -in "$WORK/cert.pem" -noout -subject -nameopt multiline | sed -n 's/^ *commonName *= *//p')"
openssl pkcs12 -export -legacy -inkey "$KEY" -in "$WORK/cert.pem" -name "$IDENTITY" \
  -passout "pass:$P12_PW" -out "$WORK/sign.p12"

security create-keychain -p "$KEYCHAIN_PW" "$KEYCHAIN"
security set-keychain-settings "$KEYCHAIN"
security unlock-keychain -p "$KEYCHAIN_PW" "$KEYCHAIN"
security import "$WORK/sign.p12" -k "$KEYCHAIN" -P "$P12_PW" -T /usr/bin/codesign >/dev/null
security set-key-partition-list -S apple-tool:,apple:,codesign: -s -k "$KEYCHAIN_PW" "$KEYCHAIN" >/dev/null
security list-keychains -d user -s "$KEYCHAIN" "${ORIGINAL_KEYCHAINS[@]}"
echo "Signing as: $IDENTITY"

npx vite build
if [[ "${1:-}" == "--universal" ]]; then
  node electron/build.mjs
  TARGET_ARGS=(--mac) # the dmg + zip targets from electron-builder.yml (universal)
else
  node electron/build.mjs --host-arch-only
  TARGET_ARGS=(--mac dir "--$(uname -m | sed 's/x86_64/x64/')")
fi

# "Developer ID Application: " is implied; electron-builder wants the rest of the name.
CSC_KEYCHAIN="$KEYCHAIN" CSC_NAME="${IDENTITY#Developer ID Application: }" \
  npx electron-builder "${TARGET_ARGS[@]}"
