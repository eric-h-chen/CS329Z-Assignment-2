#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
rm -rf /app/pipeline
cp -r "$HERE/pipeline" /app/pipeline
