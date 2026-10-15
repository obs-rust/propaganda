#!/usr/bin/env bash
# Pack the AI-vs style for long-term storage.
#   kit  : code, data, masks, Antonio, style guide, site (no footage) - safe to share
#   full : kit + source footage + 4K master - private, for cold storage
set -euo pipefail
cd "$(dirname "$0")/.."
V=$(git rev-parse --short HEAD 2>/dev/null || echo nogit)
D=archive; mkdir -p "$D"
KIT=(style tools data fonts/Antonio\[wght\].ttf docs/index.html)
tar --sort=name --exclude='__pycache__' --exclude='*.old.json' -czf "$D/ai-vs-style-kit-$V.tar.gz" "${KIT[@]}"
tar --sort=name --exclude='__pycache__' --exclude='*.old.json' -cf "$D/ai-vs-full-$V.tar" "${KIT[@]}" docs out/final_4k.mp4 marines-fixing-bugs.webm Space*FoCW8lxTPBU\].webm
(cd "$D" && sha256sum ai-vs-*-"$V".tar* > "SHA256SUMS-$V")
cat "$D/SHA256SUMS-$V"; du -h "$D"/ai-vs-*-"$V".tar*
