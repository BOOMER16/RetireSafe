#!/usr/bin/env bash
# Fetch the real public datasets used by the RetireSafe test beds.
# Everything lands in ./data (git-ignored) unless RS_DATA is set.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA="${RS_DATA:-$ROOT/data}"
mkdir -p "$DATA" && cd "$DATA"

# 1. NASA-HTTP July/Aug 1995 access logs (Internet Traffic Archive mirror)
[ -d nasa-http ] || git clone --depth 1 https://github.com/greymd/NASA-HTTP nasa-http
[ -f nasa-http/NASA_access_log_Jul95 ] || gunzip -k nasa-http/NASA_access_log_Jul95.gz

# 2. can-i-take-over-xyz takeover fingerprint catalogue
[ -d cito ] || git clone --depth 1 https://github.com/EdOverflow/can-i-take-over-xyz cito

# 3. Cisco Umbrella top-1M FQDN popularity list (updated daily; we used the 2026-10-01 copy)
if [ ! -f top-1m.csv ]; then
  curl -fsSL -o umbrella.zip https://s3-us-west-1.amazonaws.com/umbrella-static/top-1m.csv.zip
  unzip -o -q umbrella.zip
fi
echo "Data ready in $DATA"
ls -la "$DATA"
