#!/usr/bin/env bash
# chart-<surum> etiketi Chart.yaml version'iyla ayni mi ve CHANGELOG'da var mi (spec B3 K2, 9).
# Argo CD chart'i bu etiketten okur; etiket yanlis surumu gosterirse kumeye yanlis chart gider.
#   scripts/chart_etiket_kontrol.sh chart-2.1.0
set -euo pipefail

CHART=helm/tech-radar
etiket="${1:-}"
if ! [[ "$etiket" =~ ^chart-([0-9]+\.[0-9]+\.[0-9]+)$ ]]; then
  echo "::error::Etiket bicimi chart-<MAJOR.MINOR.PATCH> olmali: '$etiket'"
  exit 1
fi
surum="${BASH_REMATCH[1]}"
chart_surumu=$(sed -nE 's/^version:[[:space:]]*"?([0-9]+\.[0-9]+\.[0-9]+)"?.*$/\1/p' "$CHART/Chart.yaml")
if [ "$surum" != "$chart_surumu" ]; then
  echo "::error::Etiket $etiket ama $CHART/Chart.yaml version $chart_surumu"
  exit 1
fi
if ! grep -qE "^## \[${surum//./\.}\]" "$CHART/CHANGELOG.md"; then
  echo "::error::$CHART/CHANGELOG.md icinde '## [$surum]' basligi yok"
  exit 1
fi
echo "Etiket $etiket = Chart.yaml $chart_surumu; CHANGELOG girdisi var."
