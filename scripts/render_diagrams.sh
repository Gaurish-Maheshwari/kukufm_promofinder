#!/usr/bin/env bash
# Render every docs/graphics/*.mmd to SVG and PNG with Mermaid CLI.
# Install once: npm i -g @mermaid-js/mermaid-cli
set -euo pipefail
cd "$(dirname "$0")/../docs/graphics"
for f in *.mmd; do
  name="${f%.mmd}"
  mmdc -i "$f" -o "$name.svg" -b transparent
  mmdc -i "$f" -o "$name.png" -b white -s 2
  echo "rendered $name"
done
