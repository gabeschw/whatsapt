#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

[ -f .env ] && set -a && source .env && set +a

BINARY="${WHATSAPP_BRIDGE_BINARY:-../whatsapp-bridge/whatsapp-bridge/whatsapp-client}"
BINARY_DIR="$(cd "$(dirname "$BINARY")" && pwd)"
BINARY_NAME="$(basename "$BINARY")"

cd "$BINARY_DIR"
exec "./$BINARY_NAME" --batch --batch-idle-timeout=15 --batch-max-duration=300
