#!/usr/bin/env bash
# Helm chart'ini YALNIZ yerel Docker Desktop Kubernetes'inde dogrular (spec 8, S1-S7).
# Baska hicbir kumeye dokunmaz: baglam sabittir, betik onu degistirmez ve
# baslangicta sunucunun ve dugumlerin yerel oldugunu dogrular.
#
#   scripts/helm_yerel_dogrulama.sh imaj   # api + frontend imajlarini :fazb-yerel ile derler
#   scripts/helm_yerel_dogrulama.sh kur    # S1-S6
#   scripts/helm_yerel_dogrulama.sh sok    # S7 (uninstall + namespace silme)
set -euo pipefail

BAGLAM=docker-desktop
NS=tech-radar-dogrulama
RELEASE=tech-radar
KOK="$(cd "$(dirname "$0")/.." && pwd)"
CHART="$KOK/helm/tech-radar"
DEGERLER="$CHART/ci/yerel-values.yaml"
ETIKET=fazb-yerel
API_PORT=18000
WEB_PORT=13000
GIZLI_DIZIN="$(mktemp -d)"
# Helm 4 winget ile kurulduysa yeni kabuk acilana kadar PATH'te olmayabilir
if ! command -v helm >/dev/null 2>&1; then
  export PATH="${LOCALAPPDATA:-}/Microsoft/WinGet/Links:$PATH"
  for aday in "${LOCALAPPDATA:-}"/Microsoft/WinGet/Packages/Helm.Helm_*/windows-amd64; do
    [ -x "$aday/helm.exe" ] && export PATH="$aday:$PATH"
  done
fi
trap 'kill $(jobs -p) 2>/dev/null || true; rm -rf "$GIZLI_DIZIN"' EXIT

k() { kubectl --context "$BAGLAM" "$@"; }
h() { helm --kube-context "$BAGLAM" "$@"; }
gecti() { echo "GECTI  $*"; }
kaldi() { echo "KALDI  $*" >&2; exit 1; }

baglam_dogrula() {
  kubectl config get-contexts "$BAGLAM" >/dev/null 2>&1 || kaldi "baglam '$BAGLAM' tanimli degil"
  local kume sunucu dugumler d
  kume=$(kubectl config view -o jsonpath="{.contexts[?(@.name==\"$BAGLAM\")].context.cluster}")
  sunucu=$(kubectl config view -o jsonpath="{.clusters[?(@.name==\"$kume\")].cluster.server}")
  case "$sunucu" in
    https://127.0.0.1:*|https://localhost:*|https://kubernetes.docker.internal:*) ;;
    *) kaldi "baglam sunucusu yerel degil: '$sunucu' — hicbir sey yapilmadi" ;;
  esac
  dugumler=$(k get nodes -o jsonpath='{.items[*].metadata.name}' 2>/dev/null) \
    || kaldi "kume yanit vermiyor (Docker Desktop -> Settings -> Kubernetes acik mi?)"
  [ -n "$dugumler" ] || kaldi "dugum yok"
  for d in $dugumler; do
    case "$d" in docker-desktop|desktop-*) ;; *) kaldi "beklenmeyen dugum: $d — hicbir sey yapilmadi" ;; esac
  done
  gecti "baglam yerel: $BAGLAM ($sunucu; dugumler: $dugumler)"
}

imaj() {
  docker build -t "teknoloji-haberleri-api:$ETIKET" "$KOK"
  docker build -t "teknoloji-haberleri-frontend:$ETIKET" "$KOK/frontend"
  gecti "imajlar derlendi (:$ETIKET)"
}

imaj_kumede_mi() {
  local pod=fazb-imaj-yoklama faz="" neden="" dugumler d i
  k run "$pod" -n "$NS" --image="teknoloji-haberleri-api:$ETIKET" --image-pull-policy=Never \
    --restart=Never --command -- true >/dev/null
  for _ in $(seq 1 30); do
    faz=$(k get pod "$pod" -n "$NS" -o jsonpath='{.status.phase}')
    neden=$(k get pod "$pod" -n "$NS" -o jsonpath='{.status.containerStatuses[0].state.waiting.reason}')
    [ "$faz" = Succeeded ] && break
    [ "$neden" = ErrImageNeverPull ] && break
    sleep 2
  done
  k delete pod "$pod" -n "$NS" --wait=false >/dev/null
  if [ "$faz" = Succeeded ]; then gecti "yerel imajlar kumede gorunuyor"; return 0; fi
  [ "$neden" = ErrImageNeverPull ] || kaldi "imaj yoklamasi belirsiz (faz=$faz neden=$neden)"
  # kind tabanli Docker Desktop: imajlari dugum konteynerlerine yukle
  dugumler=$(docker ps --format '{{.Names}}' | grep -E '^desktop-(control-plane|worker[0-9]*)$' || true)
  [ -n "$dugumler" ] || kaldi "imaj kumede yok ve dugum konteyneri bulunamadi"
  for d in $dugumler; do
    for i in api frontend; do
      docker save "teknoloji-haberleri-$i:$ETIKET" | docker exec -i "$d" ctr -n k8s.io images import - >/dev/null \
        || kaldi "$d dugumune teknoloji-haberleri-$i yuklenemedi"
    done
  done
  gecti "imajlar dugumlere yuklendi ($dugumler)"
}

gizlileri_uret() {
  ( umask 077
    printf 'secrets:\n  secretKey: "%s"\n  dbPassword: "%s"\n' \
      "$(openssl rand -hex 32)" "$(openssl rand -hex 24)" > "$GIZLI_DIZIN/degerler.yaml" )
}

api_shell() {
  k exec -n "$NS" deploy/teknoloji-api -c api -- python manage.py shell -v 0 -c "$1" | tr -d '\r' | tail -1
}

kod() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
bekle_kod() {
  local beklenen=$1 gelen; shift
  gelen=$(kod "$@")
  [ "$gelen" = "$beklenen" ] || kaldi "S2 $* -> $gelen (beklenen $beklenen)"
}

port_ac() {
  k port-forward -n "$NS" svc/teknoloji-api "$API_PORT:8000" >/dev/null 2>&1 &
  k port-forward -n "$NS" svc/teknoloji-frontend "$WEB_PORT:3000" >/dev/null 2>&1 &
  for _ in $(seq 1 30); do
    if [ "$(kod "http://localhost:$API_PORT/api/v1/health/")" = 200 ] \
       && [ "$(kod "http://localhost:$WEB_PORT/")" = 200 ]; then
      return 0
    fi
    sleep 1
  done
  kaldi "port-forward acilmadi"
}

s1_kurulum() {
  h upgrade --install "$RELEASE" "$CHART" -n "$NS" -f "$DEGERLER" -f "$GIZLI_DIZIN/degerler.yaml" \
    --wait --wait-for-jobs --timeout 15m \
    || { k get pods -n "$NS"; kaldi "S1 helm install"; }
  local hazir_degil
  hazir_degil=$(k get pods -n "$NS" --field-selector=status.phase!=Succeeded \
    -o jsonpath='{range .items[*]}{.metadata.name}{" "}{range .status.conditions[?(@.type=="Ready")]}{.status}{end}{"\n"}{end}' \
    | awk '$2 != "True"')
  [ -z "$hazir_degil" ] || kaldi "S1 Ready olmayan pod: $hazir_degil"
  [ "$(k get job teknoloji-migrate-r1 -n "$NS" -o jsonpath='{.status.succeeded}')" = 1 ] \
    || kaldi "S1 teknoloji-migrate-r1 Complete degil"
  k exec -n "$NS" deploy/teknoloji-api -c api -- python manage.py migrate --check >/dev/null \
    || kaldi "S1 migrate --check"
  gecti "S1 kurulum: pod'lar Ready, teknoloji-migrate-r1 Complete, migrate --check 0"
}

s2_http() {
  port_ac
  bekle_kod 200 "http://localhost:$API_PORT/api/v1/health/"
  bekle_kod 401 "http://localhost:$API_PORT/api/v1/schema/"
  bekle_kod 200 "http://localhost:$WEB_PORT/"
  bekle_kod 200 "http://localhost:$WEB_PORT/api/v1/health/"
  bekle_kod 200 "http://localhost:$WEB_PORT/admin/login/"
  bekle_kod 200 "http://localhost:$WEB_PORT/static/admin/css/base.css"
  bekle_kod 400 -H "Host: kotu.example" "http://localhost:$API_PORT/api/v1/health/"
  gecti "S2 HTTP: health 200, schema 401, frontend/admin/static 200, sahte Host 400"
}

s3_uctan_uca() {
  k exec -n "$NS" deploy/teknoloji-worker -c worker -- python -c \
    "import urllib.request; urllib.request.urlopen('http://teknoloji-translate:5000/languages', timeout=10)" \
    || kaldi "S3 worker -> LibreTranslate /languages"
  local yanit durum=""
  yanit=$(curl -s -X POST -H 'Content-Type: application/json' -d '{}' "http://localhost:$WEB_PORT/api/sre/fetch/")
  echo "$yanit" | grep -qE '"success": *true' || kaldi "S3 cekim baslatilamadi: $yanit"
  for _ in $(seq 1 60); do
    durum=$(api_shell "from news.models import FetchRun; r = FetchRun.objects.filter(section='sre').order_by('-id').first(); print(r.status if r else 'yok')")
    [ "$durum" = success ] && break
    [ "$durum" = failure ] && kaldi "S3 FetchRun failure"
    sleep 10
  done
  [ "$durum" = success ] || kaldi "S3 10 dk icinde success olmadi (son durum: $durum)"
  gecti "S3 uctan uca: worker -> LibreTranslate 200, SRE cekimi FetchRun success"
}

fetchrun_sayisi() { api_shell "from news.models import FetchRun; print(FetchRun.objects.count())"; }

s4_upgrade() {
  local once sonra revizyon
  once=$(fetchrun_sayisi)
  h upgrade "$RELEASE" "$CHART" -n "$NS" -f "$DEGERLER" -f "$GIZLI_DIZIN/degerler.yaml" \
    --set config.app.retentionDays=91 --wait --wait-for-jobs --timeout 15m \
    || { k get pods -n "$NS"; kaldi "S4 helm upgrade"; }
  revizyon=$(h history "$RELEASE" -n "$NS" --max 1 | awk 'NR == 2 {print $1}')
  [ "$revizyon" = 2 ] || kaldi "S4 revizyon $revizyon (beklenen 2)"
  [ "$(k get job teknoloji-migrate-r2 -n "$NS" -o jsonpath='{.status.succeeded}')" = 1 ] \
    || kaldi "S4 teknoloji-migrate-r2 Complete degil"
  [ "$(k exec -n "$NS" deploy/teknoloji-worker -c worker -- printenv RETENTION_DAYS | tr -d '\r')" = 91 ] \
    || kaldi "S4 worker pod'u yeni configmap'i almadi"
  sonra=$(fetchrun_sayisi)
  [ "$sonra" -ge "$once" ] && [ "$once" -ge 1 ] || kaldi "S4 veri kaybi: FetchRun $once -> $sonra"
  gecti "S4 upgrade: revizyon 2, teknoloji-migrate-r2 Complete, pod'lar yenilendi, FetchRun $once -> $sonra"
}

s5_kalicilik() {
  local once sonra=""
  once=$(fetchrun_sayisi)
  k delete pod -n "$NS" -l app.kubernetes.io/name=teknoloji-postgresql --wait=true >/dev/null
  k rollout status deploy/teknoloji-postgresql -n "$NS" --timeout=5m >/dev/null || kaldi "S5 postgres yeniden acilmadi"
  for _ in $(seq 1 24); do
    sonra=$(fetchrun_sayisi 2>/dev/null || true)
    [[ "$sonra" =~ ^[0-9]+$ ]] && break
    sleep 5
  done
  [[ "$sonra" =~ ^[0-9]+$ ]] && [ "$sonra" -ge "$once" ] && [ "$once" -ge 1 ] \
    || kaldi "S5 veri kaybi: FetchRun $once -> $sonra"
  gecti "S5 kalicilik: postgres pod'u silindi, FetchRun $once -> $sonra (PVC + fsGroup)"
}

s6_required() {
  local cikti
  if cikti=$(h template t "$CHART" --set secrets.dbPassword=x 2>&1); then kaldi "S6 secretKey olmadan render basarili"; fi
  echo "$cikti" | grep -q "secrets.secretKey zorunlu" || kaldi "S6 secretKey mesaji yok: $cikti"
  if cikti=$(h template t "$CHART" --set secrets.secretKey=x 2>&1); then kaldi "S6 dbPassword olmadan render basarili"; fi
  echo "$cikti" | grep -q "secrets.dbPassword zorunlu" || kaldi "S6 dbPassword mesaji yok: $cikti"
  gecti "S6 required: secretKey ve dbPassword olmadan render reddedildi"
}

kur() {
  baglam_dogrula
  k get namespace "$NS" >/dev/null 2>&1 && kaldi "namespace $NS zaten var; once: $0 sok"
  local i
  for i in api frontend; do
    docker image inspect "teknoloji-haberleri-$i:$ETIKET" >/dev/null 2>&1 \
      || kaldi "imaj yok: teknoloji-haberleri-$i:$ETIKET (once: $0 imaj)"
  done
  k create namespace "$NS" >/dev/null
  imaj_kumede_mi
  gizlileri_uret
  s1_kurulum
  s2_http
  s3_uctan_uca
  s4_upgrade
  s5_kalicilik
  s6_required
  echo "TUM SENARYOLAR GECTI (S1-S6). Sokum: $0 sok"
}

sok() {
  baglam_dogrula
  h uninstall "$RELEASE" -n "$NS" --wait >/dev/null 2>&1 || true
  k delete namespace "$NS" --wait=true --timeout=5m >/dev/null 2>&1 || true
  k get namespace "$NS" >/dev/null 2>&1 && kaldi "S7 namespace silinemedi"
  local kalan=""
  for _ in $(seq 1 12); do
    kalan=$(k get pv -o jsonpath="{range .items[?(@.spec.claimRef.namespace==\"$NS\")]}{.metadata.name}{' '}{end}")
    [ -z "$kalan" ] && break
    sleep 5
  done
  [ -z "$kalan" ] || kaldi "S7 silinmemis PV: $kalan"
  if docker ps --format '{{.Names}}' | grep -qx teknoloji-api; then
    gecti "compose yigini ayakta (dokunulmadi)"
  fi
  gecti "S7 sokum: release, namespace ve PVC'ler silindi"
}

case "${1:-}" in
  imaj) imaj ;;
  kur) kur ;;
  sok) sok ;;
  *) echo "kullanim: $0 imaj|kur|sok" >&2; exit 2 ;;
esac
