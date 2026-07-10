#!/usr/bin/env bash
# Generate development RSA key pair for JWT signing.
# Run once before starting the identity API.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
KEYS_DIR="$PROJECT_DIR/keys"

mkdir -p "$KEYS_DIR"

if [ -f "$KEYS_DIR/private.pem" ] && [ -f "$KEYS_DIR/public.pem" ]; then
    echo "Keys already exist at $KEYS_DIR/"
    exit 0
fi

echo "Generating RSA key pair..."
openssl genpkey -algorithm RSA -out "$KEYS_DIR/private.pem" -pkeyopt rsa_keygen_bits:2048
openssl rsa -pubout -in "$KEYS_DIR/private.pem" -out "$KEYS_DIR/public.pem"

chmod 600 "$KEYS_DIR/private.pem"
chmod 644 "$KEYS_DIR/public.pem"

echo "Keys generated:"
echo "  Private: $KEYS_DIR/private.pem"
echo "  Public:  $KEYS_DIR/public.pem"
echo ""
echo "Add to .gitignore to prevent accidental commit of private keys."
