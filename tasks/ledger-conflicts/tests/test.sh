#!/bin/bash
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p /logs/verifier
if python "$HERE/verify.py" --app /app --tests "$HERE" --task conflicts; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
