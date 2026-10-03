#!/usr/bin/env bash
# Chart dizini taban ref'e gore degistiyse Chart.yaml version'i artmis ve
# CHANGELOG.md'de '## [surum]' basligi bulunmali (spec K7).
#   scripts/chart_surum_kontrol.sh <taban-ref>     # ornek: main, origin/main, bir SHA
# Taban ref yoksa ya da sifirsa (yeni dal, elle tetikleme) kapi atlanir.
set -euo pipefail

CHART=helm/tech-radar
taban="${1:-}"
if [ -z "$taban" ] || [ "$taban" = "0000000000000000000000000000000000000000" ]; then
  echo "Taban ref yok; chart surum kapisi atlandi."
  exit 0
fi
if ! git cat-file -e "${taban}^{commit}" 2>/dev/null; then
  echo "::error::Taban ref bulunamadi: $taban (checkout fetch-depth: 0 mi?)"
  exit 1
fi
if git diff --quiet "$taban" -- "$CHART"; then
  echo "Chart degismedi; surum kapisi gecti."
  exit 0
fi

surum_oku() { sed -nE 's/^version:[[:space:]]*"?([0-9]+\.[0-9]+\.[0-9]+)"?.*$/\1/p'; }
eski=$(git show "${taban}:${CHART}/Chart.yaml" 2>/dev/null | surum_oku || true)
yeni=$(surum_oku < "$CHART/Chart.yaml")
[ -n "$yeni" ] || { echo "::error::$CHART/Chart.yaml version okunamadi"; exit 1; }

if [ -n "$eski" ]; then
  en_buyuk=$(printf '%s\n%s\n' "$eski" "$yeni" | sort -V | tail -1)
  if [ "$eski" = "$yeni" ] || [ "$en_buyuk" != "$yeni" ]; then
    echo "::error::$CHART degisti ama Chart.yaml version artmadi ($eski -> $yeni)." \
         "SemVer: uyumsuz=MAJOR, yeni deger=MINOR, duzeltme=PATCH; CHANGELOG.md'ye de ekleyin."
    exit 1
  fi
fi
if ! grep -qE "^## \[${yeni//./\\.}\]" "$CHART/CHANGELOG.md"; then
  echo "::error::$CHART/CHANGELOG.md icinde '## [$yeni]' basligi yok"
  exit 1
fi
echo "Chart surumu ${eski:-yok} -> $yeni; CHANGELOG girdisi var."
