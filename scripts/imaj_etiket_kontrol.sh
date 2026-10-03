#!/usr/bin/env bash
# Helm render ciktisindaki imajlar surumlu mu (spec K7):
#  - her imajin acik bir etiketi var ve etiket 'latest' degil;
#  - teknoloji-haberleri-* disindaki (ucuncu taraf) her imaj digest ile sabit.
#   scripts/imaj_etiket_kontrol.sh rendered.yaml
set -euo pipefail

dosya="${1:?kullanim: $0 <render.yaml>}"
hata=0
sayi=0
while IFS= read -r imaj; do
  [ -n "$imaj" ] || continue
  sayi=$((sayi + 1))
  yalin="${imaj%%@*}"          # digest'i at
  son="${yalin##*/}"           # registry/yol'u at
  depo="${yalin%:*}"
  case "$son" in
    *:*) etiket="${son##*:}" ;;
    *) echo "::error::Etiketsiz imaj: $imaj"; hata=1; continue ;;
  esac
  if [ -z "$etiket" ] || [ "$etiket" = "latest" ]; then
    echo "::error::Kayan etiket: $imaj"; hata=1
  fi
  case "${depo##*/}" in
    teknoloji-haberleri-*) ;;
    *) case "$imaj" in
         *@sha256:*) ;;
         *) echo "::error::Ucuncu taraf imaj digest'siz: $imaj"; hata=1 ;;
       esac ;;
  esac
done < <(sed -nE 's/^[[:space:]]*(- )?image:[[:space:]]*"?([^"[:space:]]+)"?.*$/\2/p' "$dosya")

[ "$sayi" -gt 0 ] || { echo "::error::$dosya icinde imaj bulunamadi"; exit 1; }
[ "$hata" = 0 ] && echo "imaj kontrolu gecti: $sayi imaj ($dosya)"
exit "$hata"
