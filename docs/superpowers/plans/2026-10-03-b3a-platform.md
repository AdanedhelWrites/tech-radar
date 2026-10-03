# B3a — Yerel Platform (Terraform + Argo CD + Vault + VSO) — Uygulama Plani

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `yerel-platform` reposuna, yerel Docker Desktop kumesine Argo CD, Vault (Raft) ve Vault Secrets Operator'u iki asamali Terraform ile kuran, Vault'u baslatan/acan, sirlari ve GitOps deploy key'ini Vault'a yazan betikleri eklemek ve kurulumu T1-T5, T11 ile gercek kumede dogrulamak.

**Architecture:** Asama 1 (`terraform/kume`, helm + kubernetes provider) uc chart'i sabit surumlerle kurar; Vault'u `scripts/vault_baslat.sh` HTTP API ile baslatir (anahtarlar `.vault/init.json`'da, git disi, yalniz kullanici ACL'i). Asama 2 (`terraform/yapilandirma`, vault + kubernetes provider) Vault'u (audit, KV v2, Kubernetes auth, uygulama basina en az yetki) ve Argo CD'yi (projeler, VSO ile repo Secret'i, kok Application) yapilandirir; hicbir sir degeri Terraform'a girmez. Her betik ortak `scripts/ortak.sh` uzerinden baglami `docker-desktop`'a kilitler; Terraform yalniz `scripts/tf.sh` ile calisir.

**Tech Stack:** Terraform 1.16 (helm 3.3.0, kubernetes 3.3.0, vault 5.12.0), Argo CD chart 10.9.6 (v3.5.3), Vault chart 0.34.1 (Vault 2.0.4), VSO chart 1.6.0, bash (Git Bash), curl, jq, PowerShell (ACL), gh, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-03-b3-terraform-argocd-vault-design.md` (bolum 3, 4.2, 4.4, 5, 7, 8, 9, 10, 12). Ortam ve kurallar: `docs/superpowers/plans/2026-10-03-b3-devir-notu.md`. Planla celiskide asagidaki "Spec'e Gore Netlestirmeler" gecerlidir.

## Global Constraints

- **`aks-gokbulut` YASAK.** Aktif `kubectl` baglami `aks-gokbulut`'tur; hicbir komut ona guvenmez. Her `kubectl` `--context docker-desktop`, her `helm` `--kube-context docker-desktop` tasir. `kubectl config use-context` HIC calistirilmaz. Terraform YALNIZ `scripts/tf.sh` ile calisir (`init`, `plan`, `apply`, `destroy`, `test`, `providers lock`, `state` dahil); `terraform` dogrudan cagrilmaz. Betikler baslangicta baglami dogrular (`scripts/ortak.sh` `baglam_dogrula`).
- **Disariya donuk her adim kullanici onayiyla:** `yerel-gitops` reposunu acmak, deploy key eklemek/silmek, her `git push`. Push oncesi yerel gitleaks (`zricethezav/gitleaks:v8.30.1`, `--log-opts=origin/main..main`).
- **Sirlar** git'e, Terraform state'ine ve ekrana girmez (gerekirse `clip.exe` ile panoya). Sir tasiyan dosyalar yalniz kullanici ACL'iyle (`yalniz_bana`).
- **Sabit surumler:** Terraform `>= 1.16.0, < 2.0.0`; provider'lar `hashicorp/helm 3.3.0`, `hashicorp/kubernetes 3.3.0`, `hashicorp/vault 5.12.0`; chart'lar `argo-cd 10.9.6`, `vault 0.34.1`, `vault-secrets-operator 1.6.0`; araclar `ghcr.io/yannh/kubeconform:v0.7.0@sha256:85dbef6b4b312b99133decc9c6fc9495e9fc5f92293d4ff3b7e1b30f5611823c`, `koalaman/shellcheck:v0.11.0@sha256:61862eba1fcf09a484ebcc6feea46f1782532571a34ed51fedf90dd25f925a8d`, `zricethezav/gitleaks:v8.30.1`, gitleaks CI binary `8.30.1` SHA256 `551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb`, `hashicorp/setup-terraform@dfe3c3f87815947d99a8997f908cb6525fc44e9e # v4.0.1`.
- **Portlar (yalniz 127.0.0.1):** Vault 8200, Argo CD 8080, tech-radar API 18000 / frontend 13000.
- **Calisma yeri:** kod gorevleri (1-6) worktree `C:/Users/Adanedhel/Desktop/OpenCodeProjects/yerel-platform-b3a`, dal `feat/b3a-platform`. Task 7 dali canli kopyanin `main`'ine yerelde merge eder (push yok). Operasyon gorevleri (8-12) **canli kopyada** (`C:/Users/Adanedhel/Desktop/OpenCodeProjects/yerel-platform`) calisir: Terraform state'i ve `.vault/` orada kalici olmalidir (worktree silinince kaybolmasin). Operasyonda cikan bir duzeltme yeni bir worktree dalinda yapilir, merge edilir, sonra operasyon tekrarlanir. Canli kopyada dal degistirilmez.
- **Operasyon gorevleri (8-12) controller tarafindan kosulur**, alt ajana verilmez (gercek kume, sir, GitHub).
- **Depo kalibi:** ASCII Turkce kod/yorum/commit; her commit `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` satiriyla biter; `--no-ff` merge; yeni betikler `git add --chmod=+x` ile (mevcutlar 100755).
- **Git Bash dersleri:** konteyner yolu iceren her `docker run` `MSYS_NO_PATHCONV=1` ile; Python'u heredoc'ta tek tirnakli string'le yazma, dosyaya yaz.
- **Review politikasi:** gorev basina subagent review yok. Kapi = bu plandaki komutlar + controller'in bagimsiz dogrulamasi (dosyayi plandaki blokla bayt bayt karsilastirma, testleri yeniden kosturma). Riskli diff'te tek sonnet review. Implementer modeli **sonnet**.

## Olcum Sonuclari (2026-10-03, plan yazilirken)

Devir notunun "dogrulanacaklar" listesi olculdu; plan bu degerlere dayanir.

| Konu | Sonuc |
|---|---|
| Docker Desktop bellegi | `MemTotal` 16 601 722 880 bayt (15.5 GiB) >= 8 GB; 12 CPU |
| Terraform | **v1.16.4 kurulu** (winget gerekmez; guncel 1.16.5) |
| Kume | `docker-desktop` Ready, v1.36.1, sunucu `https://kubernetes.docker.internal:6443`; StorageClass `hostpath` (varsayilan); namespace'ler yalniz sistem |
| **Ilk prob** | Kumedeki pod -> `host.docker.internal:5432` (192.168.65.254) -> `yerel-postgres`, kullanici `cybernews`, scram-sha-256: **BAGLANDI** (`ssl=false`). Yedek plan (chart'in kendi PostgreSQL'i) **gerekmez** |
| Kumeden GitHub | `github.com:22`, `github.com:443`, `ssh.github.com:443` acik (SSH deploy key calisir) |
| Chart surumleri | `argo-cd` 10.9.6 (v3.5.3, 2026-10-01), `vault` 0.34.1 (Vault 2.0.4, 2026-08-13), `vault-secrets-operator` 1.6.0 (2026-09-25) |
| Provider surumleri | helm 3.3.0, kubernetes 3.3.0, vault 5.12.0. Helm provider 3.x sozdizimi dogrulandi: `kubernetes = { ... }` **nitelik** (blok degil), `set = [{ name, value }]` **liste**. Provider Helm SDK'sini kendi tasir; yerel Helm 4 ile ilgisi yok |
| Iki asamanin `terraform validate`'i | Prototipte GECTI; `providers lock -platform=windows_amd64 -platform=linux_amd64` (CI Linux) |
| `~/.kube/config` | Windows'ta kubernetes provider'inda `~` acilir (salt okunur plan ile denendi) |
| VSO CRD'leri (1.6.0) | `secrets.hashicorp.com/v1beta1`. `VaultAuth.spec`: `method` (`kubernetes`...), `mount`, `kubernetes{role, serviceAccount, audiences, tokenExpirationSeconds}`, `vaultConnectionRef`. `VaultStaticSecret.spec` zorunlu `destination, mount, path, type`; `destination{name, create, labels (create:true ister), transformation{excludeRaw}}`, `refreshAfter`, `rolloutRestartTargets[{kind: Deployment\|DaemonSet\|StatefulSet\|argo.Rollout, name}]`, `vaultAuthRef` (`ns/ad` olabilir), `hmacSecretData` (varsayilan true). `status.conditions` tipi `SecretSynced` (True/False), `RolloutRestart` |
| VSO aninda yenileme | Belgelenmis bir "force sync" annotation'i yok; ama VSO 1.6.0 VSS denetleyicisi **annotation degisikliginde** reconcile eder (`annotationChangedPredicate`) ve Vault'u yeniden okur. Kullanilan: `yerel-platform/yenile=<zaman>` |
| Vault chart | `server.ha.raft` tek replika; readiness `vault status` (kilitliyken Ready olmaz -> Terraform `wait = false`); `server.authDelegator.enabled: true` (Kubernetes auth icin TokenReview); `injector.enabled` acikca false |
| Vault 2.0 kirici degisiklikler | Yalniz `sys/rekey`, `sys/generate-root` kimlik ister, yol kanonik olmali, sablon politikalarinda joker yok. `sys/init`, `sys/unseal`, `sys/seal-status` kimliksiz. Audit `file` + `file_path=stdout` API ile acilabilir (yalniz `prefix` kisitli). Kubernetes auth rolunde `audience` yoksa uyari (ileride zorunlu) -> **`audience = "vault"`** |
| Argo CD | Application CRD'de `sources[].ref` var; `$values/<yol>` ref kaynaginin kokune gore. Hook: `argocd.argoproj.io/hook: Sync`, `hook-delete-policy: BeforeHookCreation`. Chart varsayilani `crds.keep: true`, dex ve notifications acik, `timeout.reconciliation: 120s` |
| Windows dosya izni | Git Bash diski `noacl` baglar: `chmod 600` etkisiz (`stat` 644 gosterir). Karsiligi: `icacls /inheritance:r /grant:r *<SID>:F`; kontrol PowerShell `Get-Acl`. Git Bash'in `whoami.exe`'si Windows'unkini golgeler -> SID PowerShell'den. `%TEMP%` baska SID'lere Modify miras verebiliyor -> gecici dizin de kisitlanir |
| Yerel araclar | `jq`, `openssl`, `ssh-keygen`, `python`, `curl` (mingw, `-K -` ve `@/tmp/...` calisir) var; `shellcheck` yok -> Docker imaji |

## Spec'e Gore Netlestirmeler

1. **Vault init/unseal HTTP API ile** (`kubectl exec ... vault operator init` yerine): `scripts/vault_baslat.sh` `PUT /v1/sys/init`'in yanitini dogrudan `.vault/init.json`'a yazar, unseal `PUT /v1/sys/unseal` govdesini dosyadan alir. Anahtar ve token hicbir komut satirina girmez. `init.json` bicimi API yanitidir: `keys`, `keys_base64`, `root_token`.
2. **"izin 600" = NTFS ACL:** mirasi kesilmis, yalniz kullanicinin SID'ine tam yetki (`yalniz_bana`, kontrol `yalniz_bende_mi`). T2 bunu olcer.
3. **`scripts/ortak.sh`** (spec listesinde yok): baglam korumasi, Vault API, ACL ve sir dosyasi yardimcilari tek yerde; tum betikler bunu yukler.
4. **`scripts/repo_anahtari.sh`** (spec 5.4 adimi betik oldu): anahtar uretir, Vault'a yazar, ayni basliktaki eski GitHub deploy key'ini silip yenisini salt okunur ekler. T12'de (sifirdan kurulum) yeniden kullanilir.
5. **`scripts/vault_yedek.sh`** (spec 7 "platform yukseltme oncesi Raft snapshot"): `GET /v1/sys/storage/raft/snapshot` -> `yedekler/`.
6. **`yerel-gitops` reposu ve deploy key B3a'da** (spec 12 B3b'ye yazmis): T5 ("Argo CD yerel-gitops'a baglanir; deploy key read_only") B3a kapisidir. B3a repoyu yalniz `README.md` + `apps/README.md` ile acar; icerigi ve CI'i B3b ekler.
7. **`cybernews_k8s` veritabani ve `sir_yaz.sh tech-radar` B3a'da** (spec 5.5 kurulum sirasi; T4 `kv/tech-radar/uygulama`'yi okur). Spec 12 bunu B3b'ye yazmis; 5.5'teki sira esas alindi.
8. **AppProject yol kisitlayamaz:** `platform` projesi kaynagi yalniz `yerel-gitops` reposu ve yalniz `argoproj.io/Application` nesneleri; `apps/` yolu kok Application'in `path`'idir.
9. **Kubernetes auth `audience = "vault"`** (rol) ve `audiences: ["vault"]` (VaultAuth).
10. **VSO `destination.transformation.excludeRaw: true`:** Secret'ta yalniz Vault anahtarlari olur (`_raw` yok).
11. **Argo CD degerleri:** `crds.keep: false` (T12 sokumunde CRD'ler de gider), `server.insecure: true` (yalniz port-forward), dex ve notifications kapali; `timeout.reconciliation` varsayilan 120 sn (spec "<= 3 dk").
12. **Namespace'leri Terraform tutar** (`kubernetes_namespace_v1`); `destroy` Vault'un Raft PVC'sini de siler. Vault `helm_release` `wait = false`.
13. **Kok Application ve projeler `kubernetes_manifest`** ile; asama 2'nin ikinci `plan`'i "No changes" olmazsa (Argo CD/VSO'nun yazdigi alan), yalniz o alan `computed_fields`'a eklenir (Task 9 Step 3).
14. **Baglam kilidinin testi `terraform test`** (`tests/baglam.tftest.hcl`, `expect_failures = [var.kube_context]`); provider hic yapilandirilmaz, CI'da da kosar.
15. **VSO aninda yenileme:** `kubectl annotate vaultstaticsecret <ad> yerel-platform/yenile=<zaman> --overwrite` (Olcum Sonuclari). T10/T11 ve README bunu kullanir.
16. **T11 B3a'da uygulamasiz:** kanit = kilitliyken repo Secret'i ve kok Application yerinde, VSO okuma hatasi (`SecretSynced=False`), kilit acilinca `SecretSynced=True`. `tech-radar` Application'i varsa betik uygulama health'ini de olcer; B3b T11'i yeniden kosar.
17. **T4 negatif giris** HTTP 400 ya da 403 kabul edilir (Vault surumune gore); kosul: token verilmemesi.
18. **Uygulama URL'leri `localhost`** (port-forward): Django `ALLOWED_HOSTS` `localhost` icerir, `127.0.0.1` icermez.
19. **CI (private repo):** code scanning (SARIF) yok; gitleaks her bulguda kirmizi. CI ayrica betik testlerini ve shellcheck'i kosar (`izin_test.sh` Linux'ta "atlandi").

## Dosya Haritasi (repo `yerel-platform`)

| Dosya | Sorumluluk | Gorev |
|---|---|---|
| `.gitignore` | `.vault/`, `.sirlar/`, Terraform yerel dosyalari | 1 |
| `scripts/ortak.sh` | Baglam korumasi, ACL, sir dosyasi -> JSON, Vault API, port-forward | 1 |
| `scripts/tf.sh` | Baglam korumali Terraform sarmalayicisi | 1 |
| `tests/tf_koruma_test.sh`, `tests/izin_test.sh`, `tests/env_json_test.sh` | Kumesiz birim testleri | 1 |
| `terraform/kume/{versions,variables,main}.tf`, `degerler/{argocd,vault,vso}.yaml`, `tests/baglam.tftest.hcl`, `.terraform.lock.hcl` | Asama 1 | 2 |
| `terraform/yapilandirma/{versions,variables,vault,argocd}.tf`, `tests/baglam.tftest.hcl`, `.terraform.lock.hcl` | Asama 2 | 3 |
| `scripts/vault_baslat.sh`, `vault_kilit_ac.sh`, `vault_yedek.sh`, `sir_yaz.sh`, `repo_anahtari.sh`, `arayuz.sh` | Operasyon betikleri | 4 |
| `scripts/k8s_dogrulama.sh` | T1-T5, T11 | 5 |
| `.github/workflows/ci.yml`, `README.md` | CI, belge | 6 |
| tech-radar `docs/ADR-0008-...md` | B3a sonucu | 12 |

---

### Task 0: Worktree ve on kosullar

**Files:** yok

**Interfaces:**
- Consumes: `yerel-platform` `main` @ `bb5c026`
- Produces: worktree `../yerel-platform-b3a` (dal `feat/b3a-platform`)

- [ ] **Step 1: Durumu dogrula ve worktree ac**

```bash
cd C:/Users/Adanedhel/Desktop/OpenCodeProjects/yerel-platform
git status --short
git log --oneline -1
terraform version | head -1
docker info --format '{{.MemTotal}}'
kubectl --context docker-desktop get nodes -o name
kubectl --context docker-desktop get ns argocd vault vault-secrets-operator 2>&1 | grep -c "not found"
docker inspect -f '{{.State.Health.Status}}' yerel-postgres
git worktree add ../yerel-platform-b3a -b feat/b3a-platform main
cd ../yerel-platform-b3a && git branch --show-current && ls scripts
```

Expected: status bos; `bb5c026 feat: paylasilan yerel PostgreSQL 16 ...`; `Terraform v1.16.x`; sayi >= `8589934592`; `node/docker-desktop`; `3`; `healthy`; `feat/b3a-platform`; `uygulama_ekle.sh  yedekle.sh`.

---

### Task 1: Ortak yardimcilar ve baglam korumali `tf.sh`

**Files:**
- Create: `scripts/ortak.sh`, `scripts/tf.sh`, `tests/tf_koruma_test.sh`, `tests/izin_test.sh`, `tests/env_json_test.sh`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: yok
- Produces (`scripts/ortak.sh`, `. "$(dirname "$0")/ortak.sh"` ile yuklenir; `set -euo pipefail` cagiran betikte):
  - Degiskenler: `BAGLAM=docker-desktop`, `KOK` (repo koku), `VAULT_DIZIN=$KOK/.vault`, `VAULT_INIT=$KOK/.vault/init.json`, `SIR_DIZIN=$KOK/.sirlar`, `VAULT_PORT=8200`, `VAULT_ADRES=http://127.0.0.1:8200`, `GECICI` (betik bitince silinen, yalniz kullanici ACL'li dizin), `VAULT_ISTEK_TOKEN`, `PF_PIDLERI`, `VAULT_PF_PID`.
  - `k <kubectl argumanlari>`; `gecti <mesaj>`; `kaldi <mesaj>` (stderr, exit 1); `baglam_dogrula`.
  - `yalniz_bana <yol>`; `yalniz_bende_mi <yol>` (0/1); `kullanici_sid`.
  - `env_json <dosya>` -> stdout `{"data":{...}}`.
  - `vault_baglan`; `vault_istek <YONTEM> <yol> [govde-dosyasi]` -> HTTP kodu (yanit `$GECICI/yanit.json`); `vault_muhurlu_mu` (0 = kilitli); `vault_kok_token_yukle`; `vault_kilidi_ac`; `pf_ac <ns> <hedef> <yerel:uzak>`.
- Produces (`scripts/tf.sh`): `scripts/tf.sh kume|yapilandirma <terraform komutu> [bayraklar]`; `TF_VAR_kube_context=docker-desktop`; `yapilandirma`'da (init/fmt/validate/providers/version/test disinda) Vault port-forward'u + `VAULT_ADDR`, `VAULT_TOKEN`.

- [ ] **Step 1: Testleri yaz**

`tests/tf_koruma_test.sh`:

```bash
#!/usr/bin/env bash
# scripts/tf.sh baglam korumasi testleri (spec 3.1). Gercek kumeye ve Terraform'a dokunmaz:
# PATH'in basina sahte kubectl ve terraform koyar; sahteler cagrilarini kaydeder.
#   tests/tf_koruma_test.sh
set -uo pipefail

KOK="$(cd "$(dirname "$0")/.." && pwd)"
SAHTE="$(mktemp -d)"
trap 'rm -rf "$SAHTE"' EXIT
mkdir -p "$SAHTE/bin"

cat > "$SAHTE/bin/kubectl" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "$SAHTE_LOG/kubectl.log"
case "$*" in
  "config get-contexts docker-desktop") [ -z "${SAHTE_BAGLAM_YOK:-}" ] ;;
  config\ view*context.cluster*) printf 'docker-desktop' ;;
  config\ view*cluster.server*) printf '%s' "$SAHTE_SUNUCU" ;;
  "--context docker-desktop get nodes"*) printf '%s' "$SAHTE_DUGUMLER" ;;
  *) exit 0 ;;
esac
EOF
cat > "$SAHTE/bin/terraform" <<'EOF'
#!/usr/bin/env bash
echo "TF_VAR_kube_context=${TF_VAR_kube_context:-} $*" >> "$SAHTE_LOG/terraform.log"
EOF
chmod +x "$SAHTE/bin/kubectl" "$SAHTE/bin/terraform"

export PATH="$SAHTE/bin:$PATH"
export SAHTE_LOG="$SAHTE"

basarisiz=0
calistir() {   # calistir <beklenen-cikis> <aciklama> -- <tf.sh argumanlari>
  local beklenen=$1 aciklama=$2; shift 3
  rm -f "$SAHTE/kubectl.log" "$SAHTE/terraform.log"; touch "$SAHTE/kubectl.log"
  "$KOK/scripts/tf.sh" "$@" >"$SAHTE/cikti" 2>&1
  local gelen=$?
  if [ "$gelen" = "$beklenen" ]; then
    echo "ok    $aciklama"
  else
    echo "HATA  $aciklama (cikis $gelen, beklenen $beklenen)"; sed 's/^/      /' "$SAHTE/cikti"
    basarisiz=1
  fi
}
terraform_cagrilmadi() {
  if [ -s "$SAHTE/terraform.log" ]; then echo "HATA  terraform cagrildi: $(cat "$SAHTE/terraform.log")"; basarisiz=1; fi
}

yerel() { export SAHTE_SUNUCU=https://kubernetes.docker.internal:6443 SAHTE_DUGUMLER=docker-desktop; unset SAHTE_BAGLAM_YOK; }

# 1. Yerel kume: terraform dogru dizinde ve kube_context=docker-desktop ile calisir
yerel
calistir 0 "yerel baglamda kume plan calisir" -- kume plan -input=false
grep -q "^TF_VAR_kube_context=docker-desktop -chdir=$KOK/terraform/kume plan -input=false$" "$SAHTE/terraform.log" \
  || { echo "HATA  terraform cagrisi beklenen gibi degil: $(cat "$SAHTE/terraform.log" 2>/dev/null)"; basarisiz=1; }

# 2. Uzak sunucu (aks-gokbulut benzeri): hicbir sey calismaz
export SAHTE_SUNUCU=https://aks-gokbulut-dns-0a1b2c.hcp.westeurope.azmk8s.io:443
calistir 1 "uzak sunucuda reddedilir" -- kume apply -auto-approve
terraform_cagrilmadi
grep -q "yerel degil" "$SAHTE/cikti" || { echo "HATA  'yerel degil' mesaji yok"; basarisiz=1; }

# 3. Yerel adres ama beklenmeyen dugum
yerel; export SAHTE_DUGUMLER="aks-nodepool1-12345678-vmss000000"
calistir 1 "beklenmeyen dugumde reddedilir" -- kume plan
terraform_cagrilmadi

# 4. Baglam tanimli degil
yerel; export SAHTE_BAGLAM_YOK=1
calistir 1 "baglam yoksa reddedilir" -- kume plan
terraform_cagrilmadi

# 5. Gecersiz asama / eksik komut
yerel
calistir 2 "gecersiz asama reddedilir" -- uretim plan
terraform_cagrilmadi
calistir 2 "komutsuz cagri reddedilir" -- kume
terraform_cagrilmadi

# 6. kube_context / -chdir / kubeconfig komut satirindan degistirilemez
calistir 1 "-var kube_context reddedilir" -- kume apply -var kube_context=aks-gokbulut
terraform_cagrilmadi
calistir 1 "-chdir reddedilir" -- kume plan -chdir=/baska
terraform_cagrilmadi
calistir 1 "-var kubeconfig reddedilir" -- kume plan -var kubeconfig=/baska/config
terraform_cagrilmadi

# 7. Hicbir cagri use-context kullanmaz; kumeye giden her cagri --context docker-desktop tasir
yerel
calistir 0 "yapilandirma init (Vault gerekmez)" -- yapilandirma init -backend=false
if grep -q "use-context" "$SAHTE/kubectl.log"; then echo "HATA  use-context cagrildi"; basarisiz=1; fi
if grep -v "^config " "$SAHTE/kubectl.log" | grep -qv "^--context docker-desktop "; then
  echo "HATA  baglamsiz kubectl cagrisi:"; grep -v "^config " "$SAHTE/kubectl.log"; basarisiz=1
fi

# 8. yapilandirma test Vault'a baglanmaz (baglam testi provider yapilandirmaz)
yerel
calistir 0 "yapilandirma test (Vault gerekmez)" -- yapilandirma test
grep -q -- "-chdir=$KOK/terraform/yapilandirma test$" "$SAHTE/terraform.log"   || { echo "HATA  yapilandirma test terraform'a ulasmadi"; basarisiz=1; }

[ "$basarisiz" = 0 ] && echo "TUM TESTLER GECTI" || { echo "TESTLER BASARISIZ"; exit 1; }
```

`tests/izin_test.sh`:

```bash
#!/usr/bin/env bash
# ortak.sh yalniz_bana / yalniz_bende_mi testleri (yalniz Windows; NTFS ACL).
#   tests/izin_test.sh
set -uo pipefail
. "$(dirname "$0")/../scripts/ortak.sh"
if ! command -v powershell.exe >/dev/null 2>&1; then echo "atlandi: Windows degil"; exit 0; fi

basarisiz=0
bekle() {   # bekle <0|1> <aciklama> <yol>
  if yalniz_bende_mi "$3"; then gelen=0; else gelen=1; fi
  if [ "$gelen" = "$1" ]; then echo "ok    $2"; else echo "HATA  $2 (gelen $gelen)"; basarisiz=1; fi
}

D="$KOK/.izin-testi"
rm -rf "$D"; mkdir -p "$D"
echo x > "$D/miras"
bekle 1 "yeni dosya mirasli ACL tasir (yalniz bende degil)" "$D/miras"
yalniz_bana "$D/miras"
bekle 0 "yalniz_bana sonrasi dosya yalniz bende" "$D/miras"
[ "$(cat "$D/miras")" = x ] && echo "ok    dosya hala okunabilir" || { echo "HATA  dosya okunamiyor"; basarisiz=1; }

mkdir -p "$D/dizin"
yalniz_bana "$D/dizin"
echo y > "$D/dizin/icerik"
bekle 0 "kisitli dizinde olusan dosya yalniz bende" "$D/dizin/icerik"
bekle 0 "kisitli dizin yalniz bende" "$D/dizin"

bekle 0 "ortak.sh GECICI dizini yalniz bende" "$GECICI"

rm -rf "$D" || basarisiz=1
[ "$basarisiz" = 0 ] && echo "TUM TESTLER GECTI" || { echo "TESTLER BASARISIZ"; exit 1; }
```

`tests/env_json_test.sh`:

```bash
#!/usr/bin/env bash
# ortak.sh env_json testleri (sir dosyasi -> KV v2 govdesi). Kumeye dokunmaz.
#   tests/env_json_test.sh
set -uo pipefail
. "$(dirname "$0")/../scripts/ortak.sh"

basarisiz=0
esit() {   # esit <aciklama> <gelen> <beklenen>
  if [ "$2" = "$3" ]; then echo "ok    $1"; else echo "HATA  $1"; echo "      gelen:    $2"; echo "      beklenen: $3"; basarisiz=1; fi
}

D="$GECICI/test"; mkdir -p "$D"

printf '# yorum\n\nSECRET_KEY=abc=def\r\nDB_USER=cybernews_k8s\nGEMINI_API_KEY=\n  # girintili yorum\n' > "$D/iyi.env"
esit "anahtarlar, '=' iceren deger, bos deger, CRLF" \
  "$(env_json "$D/iyi.env" | jq -cS .)" \
  '{"data":{"DB_USER":"cybernews_k8s","GEMINI_API_KEY":"","SECRET_KEY":"abc=def"}}'

printf 'SIFRE=gizli-deger-123\nbu satir bozuk\n' > "$D/bozuk.env"
cikti=$( (env_json "$D/bozuk.env") 2>&1 ); kod=$?
esit "bicimsiz satirda hata" "$kod" 1
case "$cikti" in *"gizli-deger-123"*) echo "HATA  hata mesaji deger sizdirdi"; basarisiz=1 ;; *) echo "ok    hata mesajinda deger yok" ;; esac
case "$cikti" in *"satir(lar): 2 "*) echo "ok    satir numarasi verildi" ;; *) echo "HATA  satir numarasi yok: $cikti"; basarisiz=1 ;; esac

printf '# yalniz yorum\n' > "$D/bos.env"
( env_json "$D/bos.env" ) >/dev/null 2>&1; esit "anahtarsiz dosya reddedilir" "$?" 5

( env_json "$D/yok.env" ) >/dev/null 2>&1; esit "olmayan dosya reddedilir" "$?" 1

[ "$basarisiz" = 0 ] && echo "TUM TESTLER GECTI" || { echo "TESTLER BASARISIZ"; exit 1; }
```

- [ ] **Step 2: Testleri calistir, kirmiziyi gor**

```bash
cd C:/Users/Adanedhel/Desktop/OpenCodeProjects/yerel-platform-b3a
bash tests/tf_koruma_test.sh | tail -3; bash tests/env_json_test.sh 2>&1 | tail -1
```

Expected: kirmizi. tf_koruma: `HATA  ...` satirlari (`scripts/tf.sh: No such file or directory`) ve `TESTLER BASARISIZ`; env_json: `scripts/ortak.sh: No such file or directory` ve `GECICI: unbound variable`. `TUM TESTLER GECTI` basilmaz.

- [ ] **Step 3: `scripts/ortak.sh`**

```bash
# shellcheck shell=bash disable=SC2034  # degiskenleri yukleyen betikler kullanir
# Ortak yardimcilar: baglam korumasi (spec 3.1), Vault API, dosya izinleri.
# Kaynak olarak yuklenir:  . "$(dirname "$0")/ortak.sh"
#
# Kural: kumeye dokunan her komut `k` (kubectl --context docker-desktop) ile calisir;
# `kubectl config use-context` hic cagrilmaz. Sirlar komut satirina ve ciktiya yazilmaz:
# Vault token'i curl'e stdin'deki yapilandirmayla (-K -), govdeler GECICI dizindeki
# dosyalarla gider; yanitlar GECICI/yanit.json'a yazilir, ekrana basilmaz.

BAGLAM=docker-desktop
KOK="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VAULT_DIZIN="$KOK/.vault"
VAULT_INIT="$VAULT_DIZIN/init.json"
SIR_DIZIN="$KOK/.sirlar"
VAULT_PORT=8200
VAULT_ADRES="http://127.0.0.1:$VAULT_PORT"
GECICI="$(mktemp -d)"
VAULT_ISTEK_TOKEN=""
PF_PIDLERI=""
VAULT_PF_PID=""

temizle() {
  local p
  for p in $PF_PIDLERI $VAULT_PF_PID; do kill "$p" 2>/dev/null || true; done
  rm -rf "$GECICI"
}
trap temizle EXIT

k() { kubectl --context "$BAGLAM" "$@"; }
gecti() { echo "GECTI  $*"; }
kaldi() { echo "KALDI  $*" >&2; exit 1; }

# Baglam yerel mi: sunucu 127.0.0.1/localhost/kubernetes.docker.internal ve dugumler
# docker-desktop/desktop-* olmali. Degilse hicbir sey yapmadan cikar.
baglam_dogrula() {
  kubectl config get-contexts "$BAGLAM" >/dev/null 2>&1 || kaldi "baglam '$BAGLAM' tanimli degil"
  local kume sunucu dugumler d
  kume=$(kubectl config view -o jsonpath="{.contexts[?(@.name==\"$BAGLAM\")].context.cluster}")
  sunucu=$(kubectl config view -o jsonpath="{.clusters[?(@.name==\"$kume\")].cluster.server}")
  case "$sunucu" in
    https://127.0.0.1:*|https://localhost:*|https://kubernetes.docker.internal:*) ;;
    *) kaldi "baglam sunucusu yerel degil: '$sunucu' - hicbir sey yapilmadi" ;;
  esac
  dugumler=$(k get nodes -o jsonpath='{.items[*].metadata.name}' 2>/dev/null) \
    || kaldi "kume yanit vermiyor (Docker Desktop -> Settings -> Kubernetes acik mi?)"
  [ -n "$dugumler" ] || kaldi "dugum yok"
  for d in $dugumler; do
    case "$d" in docker-desktop|desktop-*) ;; *) kaldi "beklenmeyen dugum: $d - hicbir sey yapilmadi" ;; esac
  done
  echo "baglam yerel: $BAGLAM ($sunucu; dugumler: $dugumler)"
}

# --- Dosya izinleri (Windows/NTFS) -------------------------------------------------------
# Git Bash diski `noacl` baglar: chmod 600 etkisizdir. "600"un karsiligi: mirasi kesilmis,
# yalniz bu kullanicinin SID'ine tam yetki veren ACL.
kullanici_sid() {   # Git Bash'in kendi whoami.exe'si Windows'unkini golgeler: PowerShell
  powershell.exe -NoProfile -NonInteractive -Command \
    "[Security.Principal.WindowsIdentity]::GetCurrent().User.Value" | tr -d '\r'
}

yalniz_bana() {   # yalniz_bana <dosya|dizin>
  local sid hak=F
  sid=$(kullanici_sid)
  [[ "$sid" =~ ^S-1-5- ]] || kaldi "kullanici SID'i okunamadi"
  [ -d "$1" ] && hak='(OI)(CI)F'
  MSYS_NO_PATHCONV=1 icacls "$(cygpath -w "$1")" /inheritance:r /grant:r "*${sid}:${hak}" >/dev/null \
    || kaldi "izin ayarlanamadi: $1"
}

yalniz_bende_mi() {   # yalniz_bende_mi <yol> -> 0: tek kural, bu kullanici, FullControl
  local w
  w=$(cygpath -w "$1")
  MSYS_NO_PATHCONV=1 powershell.exe -NoProfile -NonInteractive -Command \
    "\$r = @((Get-Acl -LiteralPath '$w').Access); \$ben = [Security.Principal.WindowsIdentity]::GetCurrent().User; if (\$r.Count -eq 1 -and \$r[0].IdentityReference.Translate([Security.Principal.SecurityIdentifier]) -eq \$ben -and \$r[0].FileSystemRights -match 'FullControl') { exit 0 } else { exit 1 }"
}

# --- Sir dosyalari -----------------------------------------------------------------------

# env_json <dosya> -> stdout: {"data": {"ANAHTAR": "deger", ...}} (KV v2 yazma govdesi).
# Satirlar: ANAHTAR=deger, bos ya da '#' ile baslayan. Deger tirnaksiz, oldugu gibi alinir
# (CRLF temizlenir). Bicimsiz satirda satir numarasini (icerigi degil) soyleyip cikar.
env_json() {
  local dosya=$1 bozuk
  [ -f "$dosya" ] || kaldi "dosya yok: $dosya"
  bozuk=$(tr -d '\r' < "$dosya" | grep -nvE '^([A-Za-z_][A-Za-z0-9_]*=.*|[[:space:]]*#.*|[[:space:]]*)$' | cut -d: -f1 | tr '\n' ' ')
  [ -z "$bozuk" ] || kaldi "$dosya bicimsiz satir(lar): $bozuk(beklenen ANAHTAR=deger)"
  tr -d '\r' < "$dosya" | jq -Rn '
    [inputs | select(test("^[A-Za-z_][A-Za-z0-9_]*="))
            | capture("^(?<k>[A-Za-z_][A-Za-z0-9_]*)=(?<v>.*)$")]
    | if length == 0 then error("anahtar yok") else . end
    | {data: (map({(.k): .v}) | add)}'
}

# --- Vault --------------------------------------------------------------------------------

# 127.0.0.1:8200 yanit vermiyorsa vault-0'a port-forward acar (kilitliyken de calisir);
# betik bitince kapanir. Pod yeniden olusursa tekrar cagirin: eski port-forward kapatilir.
vault_baglan() {
  local _
  if curl -s -o /dev/null --max-time 2 "$VAULT_ADRES/v1/sys/seal-status"; then return 0; fi
  if [ -n "$VAULT_PF_PID" ]; then kill "$VAULT_PF_PID" 2>/dev/null || true; sleep 1; fi
  kubectl --context "$BAGLAM" port-forward -n vault pod/vault-0 "$VAULT_PORT:8200" >/dev/null 2>&1 &
  VAULT_PF_PID=$!
  for _ in $(seq 1 30); do
    curl -s -o /dev/null --max-time 2 "$VAULT_ADRES/v1/sys/seal-status" && return 0
    sleep 1
  done
  kaldi "Vault'a port-forward acilamadi (vault-0 calisiyor mu?)"
}

# vault_istek <YONTEM> <yol> [govde-dosyasi] -> HTTP kodu; yanit GECICI/yanit.json.
# Token VAULT_ISTEK_TOKEN'dan (bossa basliksiz: or. auth/kubernetes/login).
vault_istek() {
  local yontem=$1 yol=$2 govde=${3:-}
  local veri=()
  [ -n "$govde" ] && veri=(--data-binary "@$govde")
  { if [ -n "$VAULT_ISTEK_TOKEN" ]; then printf 'header = "X-Vault-Token: %s"\n' "$VAULT_ISTEK_TOKEN"; fi; } \
    | curl -s -K - -X "$yontem" -o "$GECICI/yanit.json" -w '%{http_code}' "${veri[@]}" "$VAULT_ADRES/v1/$yol"
}

# Port-forward acar ve betik bitince kapatir: pf_ac <namespace> <hedef> <yerel-port>:<uzak-port>
pf_ac() {
  kubectl --context "$BAGLAM" port-forward -n "$1" "$2" "$3" >/dev/null 2>&1 &
  PF_PIDLERI="$PF_PIDLERI $!"
}

vault_muhurlu_mu() {   # 0: kilitli, 1: acik
  [ "$(curl -s "$VAULT_ADRES/v1/sys/seal-status" | jq -r .sealed)" = true ]
}

vault_kok_token_yukle() {
  [ -f "$VAULT_INIT" ] || kaldi "$VAULT_INIT yok: once scripts/vault_baslat.sh"
  VAULT_ISTEK_TOKEN=$(jq -r .root_token "$VAULT_INIT")
  [ -n "$VAULT_ISTEK_TOKEN" ] && [ "$VAULT_ISTEK_TOKEN" != null ] || kaldi "$VAULT_INIT icinde root_token yok"
}

# Kilidi .vault/init.json'daki anahtarla acar (spec 5.2). Anahtar dosyadan dosyaya gider.
vault_kilidi_ac() {
  [ -f "$VAULT_INIT" ] || kaldi "$VAULT_INIT yok: once scripts/vault_baslat.sh"
  vault_muhurlu_mu || { echo "Vault zaten acik"; return 0; }
  jq '{key: .keys_base64[0]}' "$VAULT_INIT" > "$GECICI/anahtar.json"
  local kod
  kod=$(curl -s -X PUT -o "$GECICI/yanit.json" -w '%{http_code}' --data-binary "@$GECICI/anahtar.json" \
    "$VAULT_ADRES/v1/sys/unseal")
  rm -f "$GECICI/anahtar.json"
  [ "$kod" = 200 ] || kaldi "unseal HTTP $kod"
  [ "$(jq -r .sealed "$GECICI/yanit.json")" = false ] || kaldi "unseal sonrasi hala kilitli"
}

# GECICI sir tasiyan dosyalar barindirir: Windows'ta yalniz bu kullanici erisir
# (%TEMP% baska SID'lere de yazma izni miras verebilir).
if command -v powershell.exe >/dev/null 2>&1; then yalniz_bana "$GECICI"; fi
```

- [ ] **Step 4: `scripts/tf.sh`**

```bash
#!/usr/bin/env bash
# Baglam korumali Terraform sarmalayicisi (spec 3.1). Terraform'u YALNIZ bununla calistirin.
#
#   scripts/tf.sh kume init|plan|apply|destroy|test|output|state ... [terraform bayraklari]
#   scripts/tf.sh yapilandirma init|plan|apply|destroy|test|output|state ...
#
# Once baglamin yerel oldugunu dogrular; degilse terraform hic calismaz. kube_context
# her zaman docker-desktop'tir (TF_VAR); komut satirindan degistirilemez.
# yapilandirma asamasinda Vault port-forward'unu acar ve VAULT_ADDR/VAULT_TOKEN'i
# .vault/init.json'dan verir (token ekrana basilmaz).
set -euo pipefail
. "$(dirname "$0")/ortak.sh"

kullanim() { echo "kullanim: $0 kume|yapilandirma <terraform komutu> [bayraklar]" >&2; exit 2; }

asama="${1:-}"
komut="${2:-}"
case "$asama" in kume|yapilandirma) ;; *) kullanim ;; esac
[ -n "$komut" ] || kullanim
shift 2
for arg in "$@"; do
  case "$arg" in
    *kube_context*|-chdir*|*kubeconfig*) kaldi "'$arg' verilemez: baglam ve kubeconfig sabittir" ;;
  esac
done

baglam_dogrula
export TF_VAR_kube_context="$BAGLAM"

if [ "$asama" = yapilandirma ]; then
  case "$komut" in
    init|fmt|validate|providers|version|test) ;;
    *)
      vault_baglan
      vault_muhurlu_mu && kaldi "Vault kilitli: once scripts/vault_kilit_ac.sh"
      vault_kok_token_yukle
      export VAULT_ADDR="$VAULT_ADRES"
      export VAULT_TOKEN="$VAULT_ISTEK_TOKEN"
      ;;
  esac
fi

# exec degil: cikista port-forward kapanmali (trap)
terraform -chdir="$KOK/terraform/$asama" "$komut" "$@"
```

- [ ] **Step 5: `.gitignore`'a ekle** (dosyanin sonuna)

```gitignore

# B3: Vault anahtarlari ve uygulama sirlari (yalniz yerel, kullanici ACL'li)
.vault/
.sirlar/

# Terraform yerel dosyalari (state sir icermez ama makineye ozeldir; .terraform.lock.hcl girer)
**/.terraform/
*.tfstate
*.tfstate.*
*.tfplan
crash.log

# tests/izin_test.sh calisma dizini
.izin-testi/
```

- [ ] **Step 6: Testleri calistir, yesili gor**

```bash
bash tests/tf_koruma_test.sh && bash tests/izin_test.sh && bash tests/env_json_test.sh
```

Expected: uc dosya da `TUM TESTLER GECTI` (tf_koruma 11 `ok`, izin 6 `ok`, env_json 6 `ok`).

- [ ] **Step 7: Mutasyon kontrolu (test gercekten koruyor mu)**

```bash
cp scripts/tf.sh /tmp/tf.yedek
sed -i 's/^baglam_dogrula$/: baglam_dogrula/' scripts/tf.sh
bash tests/tf_koruma_test.sh | grep -cE '^HATA'
cp /tmp/tf.yedek scripts/tf.sh
bash tests/tf_koruma_test.sh | tail -1
```

Expected: HATA sayisi >= 3 (uzak sunucu, beklenmeyen dugum, baglam yok); geri alininca `TUM TESTLER GECTI`.

- [ ] **Step 8: shellcheck**

```bash
MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W):/mnt" -w /mnt \
  koalaman/shellcheck:v0.11.0@sha256:61862eba1fcf09a484ebcc6feea46f1782532571a34ed51fedf90dd25f925a8d \
  -x -S warning scripts/*.sh tests/*.sh && echo shellcheck-temiz
```

Expected: `shellcheck-temiz`.

- [ ] **Step 9: Commit**

```bash
git add .gitignore
git add --chmod=+x scripts/ortak.sh scripts/tf.sh tests/tf_koruma_test.sh tests/izin_test.sh tests/env_json_test.sh
git commit -m "feat: baglam korumali tf.sh ve ortak yardimcilar (B3a)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Asama 1 — `terraform/kume` (Argo CD, Vault, VSO)

**Files:**
- Create: `terraform/kume/versions.tf`, `variables.tf`, `main.tf`, `degerler/argocd.yaml`, `degerler/vault.yaml`, `degerler/vso.yaml`, `tests/baglam.tftest.hcl`, `.terraform.lock.hcl` (uretilir)

**Interfaces:**
- Consumes: `scripts/tf.sh` (Task 1)
- Produces: kumede namespace'ler `argocd`, `vault`, `vault-secrets-operator`; release'ler `argocd`, `vault`, `vault-secrets-operator`. Kaynak adlari (Task 4-5 ve B3b kullanir): Deployment `argocd-server`, `argocd-repo-server`, `argocd-redis`, `argocd-applicationset-controller`, StatefulSet `argocd-application-controller`, Secret `argocd-initial-admin-secret`; StatefulSet `vault`, pod `vault-0`, Service `vault` (8200), PVC `data-vault-0`; Deployment `vault-secrets-operator-controller-manager`, `VaultConnection` `vault-secrets-operator/default` (`http://vault.vault.svc:8200`).

- [ ] **Step 1: Baglam testini yaz** — `terraform/kume/tests/baglam.tftest.hcl`:

```hcl
# Baglam kilidi (spec 3.1): docker-desktop disindaki her baglam degisken dogrulamasinda
# reddedilir; provider hic yapilandirilmaz. Calistirma: scripts/tf.sh <asama> test
run "baska_baglam_reddedilir" {
  command = plan

  variables {
    kube_context = "baska-kume"
  }

  expect_failures = [var.kube_context]
}
```

- [ ] **Step 2: Kirmiziyi gor**

```bash
scripts/tf.sh kume init -input=false >/dev/null && scripts/tf.sh kume test -no-color | tail -2
```

Expected: `Failure! 0 passed, 1 failed.`

- [ ] **Step 3: `terraform/kume/versions.tf`**

```hcl
# Asama 1: Argo CD, Vault, Vault Secrets Operator (spec 5.1).
# Yalniz scripts/tf.sh ile calistirin: baglami dogrular ve kube_context'i verir.
terraform {
  required_version = ">= 1.16.0, < 2.0.0"

  required_providers {
    helm = {
      source  = "hashicorp/helm"
      version = "3.3.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "3.3.0"
    }
  }
}
```

- [ ] **Step 4: `terraform/kume/variables.tf`**

```hcl
variable "kube_context" {
  description = "Kubernetes baglami. Yalniz yerel Docker Desktop kumesi kabul edilir (spec 3.1); scripts/tf.sh verir."
  type        = string

  validation {
    condition     = var.kube_context == "docker-desktop"
    error_message = "Yalniz 'docker-desktop' baglami kabul edilir. Terraform'u scripts/tf.sh ile calistirin."
  }
}

variable "kubeconfig" {
  description = "kubeconfig dosyasi."
  type        = string
  default     = "~/.kube/config"
}
```

- [ ] **Step 5: `terraform/kume/main.tf`**

```hcl
provider "kubernetes" {
  config_path    = var.kubeconfig
  config_context = var.kube_context
}

provider "helm" {
  kubernetes = {
    config_path    = var.kubeconfig
    config_context = var.kube_context
  }
}

# Namespace'leri Terraform tutar: destroy, Vault'un Raft PVC'sini de siler (T12).
resource "kubernetes_namespace_v1" "platform" {
  for_each = toset(["argocd", "vault", "vault-secrets-operator"])

  metadata {
    name = each.key
  }
}

# Chart surumleri sabit (2026-10-03 itibariyle guncel kararli). Yukseltme: surumu degistir,
# scripts/tf.sh kume plan, sonra apply (Vault icin once Raft snapshot; spec 7).
resource "helm_release" "argocd" {
  name       = "argocd"
  repository = "https://argoproj.github.io/argo-helm"
  chart      = "argo-cd"
  version    = "10.9.6"
  namespace  = kubernetes_namespace_v1.platform["argocd"].metadata[0].name
  values     = [file("${path.module}/degerler/argocd.yaml")]
  wait       = true
  timeout    = 900
}

resource "helm_release" "vault" {
  name       = "vault"
  repository = "https://helm.releases.hashicorp.com"
  chart      = "vault"
  version    = "0.34.1"
  namespace  = kubernetes_namespace_v1.platform["vault"].metadata[0].name
  values     = [file("${path.module}/degerler/vault.yaml")]
  # vault-0 init + unseal'a kadar Ready olmaz (readiness `vault status`): beklenmez.
  # Baslatma: scripts/vault_baslat.sh
  wait    = false
  timeout = 600
}

resource "helm_release" "vso" {
  name       = "vault-secrets-operator"
  repository = "https://helm.releases.hashicorp.com"
  chart      = "vault-secrets-operator"
  version    = "1.6.0"
  namespace  = kubernetes_namespace_v1.platform["vault-secrets-operator"].metadata[0].name
  values     = [file("${path.module}/degerler/vso.yaml")]
  wait       = true
  timeout    = 600

  depends_on = [helm_release.vault]
}
```

- [ ] **Step 6: Degerler**

`terraform/kume/degerler/argocd.yaml`:

```yaml
# Argo CD (spec 5.1). Arayuz yalniz port-forward ile: scripts/arayuz.sh argocd
crds:
  # Sokumde (T12) CRD'ler de silinir; kalirsa yeniden kurulum eski Application'lari gorur
  keep: false
configs:
  params:
    # TLS'i port-forward'in arkasinda acmaya gerek yok (yalniz 127.0.0.1)
    server.insecure: true
# SSO ve bildirim yok (spec 10)
dex:
  enabled: false
notifications:
  enabled: false
```

`terraform/kume/degerler/vault.yaml`:

```yaml
# Vault (spec 5.1): tek dugum, Raft depolama (PVC), dev modu degil.
# Arayuz yalniz port-forward ile: scripts/arayuz.sh vault
injector:
  # Sirlari VSO tasir (spec K3)
  enabled: false
ui:
  enabled: true
server:
  dataStorage:
    size: 1Gi
  ha:
    enabled: true
    replicas: 1
    raft:
      enabled: true
      setNodeId: true
```

`terraform/kume/degerler/vso.yaml`:

```yaml
# Vault Secrets Operator (spec 5.1). VaultAuth'lar vaultConnectionRef vermezse bu
# varsayilan baglantiyi (vault-secrets-operator/default) kullanir.
defaultVaultConnection:
  enabled: true
  address: http://vault.vault.svc:8200
```

- [ ] **Step 7: init, iki platform icin kilit, fmt, validate, test**

```bash
scripts/tf.sh kume init -input=false -upgrade >/dev/null
scripts/tf.sh kume providers lock -platform=windows_amd64 -platform=linux_amd64 | grep -E '^Success!'
grep -cE '^provider ' terraform/kume/.terraform.lock.hcl
scripts/tf.sh kume fmt -check -recursive && echo fmt-ok
scripts/tf.sh kume validate -no-color
scripts/tf.sh kume test -no-color | tail -1
```

Expected: `Success! Terraform has updated the lock file.` (ya da `...validated the lock file...`); `2`; `fmt-ok`; `Success! The configuration is valid.`; `Success! 1 passed, 0 failed.`

- [ ] **Step 8: Mutasyon kontrolu**

```bash
cp terraform/kume/variables.tf /tmp/v.yedek
sed -i 's/condition     = var.kube_context == "docker-desktop"/condition     = length(var.kube_context) > 0/' terraform/kume/variables.tf
scripts/tf.sh kume test -no-color 2>&1 | grep -E 'Missing expected failure|failed' | head -2
cp /tmp/v.yedek terraform/kume/variables.tf
scripts/tf.sh kume test -no-color | tail -1
```

Expected: `Error: Missing expected failure` ve `Failure! 0 passed, 1 failed.`; geri alininca `Success! 1 passed, 0 failed.`

- [ ] **Step 9: Commit**

```bash
git add terraform/kume
git status --short terraform/kume | grep -c tfstate   # 0
git commit -m "feat: terraform kume asamasi (Argo CD 10.9.6, Vault 0.34.1, VSO 1.6.0)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Asama 2 — `terraform/yapilandirma` (Vault ayarlari, projeler, kok Application)

**Files:**
- Create: `terraform/yapilandirma/versions.tf`, `variables.tf`, `vault.tf`, `argocd.tf`, `tests/baglam.tftest.hcl`, `.terraform.lock.hcl` (uretilir)

**Interfaces:**
- Consumes: Task 2'nin kurdugu CRD'ler (`argoproj.io`, `secrets.hashicorp.com`), `scripts/tf.sh`
- Produces (Task 4-5 ve B3b kullanir):
  - Vault: audit `stdout`; KV v2 `kv/`; auth `kubernetes/` (`kubernetes_host = https://kubernetes.default.svc`); politika + rol `tech-radar` (yalniz `tech-radar` ns'teki SA `tech-radar-vso`, `kv/data/tech-radar/*` okuma, audience `vault`); politika + rol `argocd-repo` (yalniz `argocd` ns'teki SA `argocd-vso`, `kv/data/argocd/*` okuma).
  - Kubernetes: SA `argocd/argocd-vso`; `VaultAuth argocd/argocd-vso`; `VaultStaticSecret argocd/yerel-gitops-repo` (`kv/argocd/yerel-gitops` -> Secret `repo-yerel-gitops`, etiket `argocd.argoproj.io/secret-type: repository`); AppProject `platform`, `kisisel`; Application `argocd/kok` (`git@github.com:AdanedhelWrites/yerel-gitops.git`, `main`, `apps`, automated prune+selfHeal, finalizer).
  - Degisken `uygulamalar` (varsayilan `["tech-radar"]`), `gitops_repo`, `uygulama_repolari`.

- [ ] **Step 1: Baglam testi** — `terraform/yapilandirma/tests/baglam.tftest.hcl`:

```hcl
# Baglam kilidi (spec 3.1): docker-desktop disindaki her baglam degisken dogrulamasinda
# reddedilir; provider hic yapilandirilmaz. Calistirma: scripts/tf.sh <asama> test
run "baska_baglam_reddedilir" {
  command = plan

  variables {
    kube_context = "baska-kume"
  }

  expect_failures = [var.kube_context]
}
```

- [ ] **Step 2: Kirmiziyi gor**

```bash
scripts/tf.sh yapilandirma init -input=false >/dev/null && scripts/tf.sh yapilandirma test -no-color | tail -1
```

Expected: `Failure! 0 passed, 1 failed.` (`test` Vault istemez; tf.sh Task 1'den beri Vault'a baglanmadan calistirir.)

- [ ] **Step 3: `terraform/yapilandirma/versions.tf`**

```hcl
# Asama 2: Vault ayarlari, Argo CD projeleri, repo erisimi, kok Application (spec 5.3).
# Yalniz scripts/tf.sh ile calistirin: baglami dogrular, Vault port-forward'unu acar,
# VAULT_ADDR/VAULT_TOKEN'i .vault/init.json'dan verir. Hicbir sir degeri Terraform'a girmez.
terraform {
  required_version = ">= 1.16.0, < 2.0.0"

  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "3.3.0"
    }
    vault = {
      source  = "hashicorp/vault"
      version = "5.12.0"
    }
  }
}
```

- [ ] **Step 4: `terraform/yapilandirma/variables.tf`**

```hcl
variable "kube_context" {
  description = "Kubernetes baglami. Yalniz yerel Docker Desktop kumesi kabul edilir (spec 3.1); scripts/tf.sh verir."
  type        = string

  validation {
    condition     = var.kube_context == "docker-desktop"
    error_message = "Yalniz 'docker-desktop' baglami kabul edilir. Terraform'u scripts/tf.sh ile calistirin."
  }
}

variable "kubeconfig" {
  description = "kubeconfig dosyasi."
  type        = string
  default     = "~/.kube/config"
}

variable "uygulamalar" {
  description = "Kisisel uygulamalar. Her biri icin Vault politikasi + rolu ve Argo CD hedef namespace'i olusur."
  type        = list(string)
  default     = ["tech-radar"]

  validation {
    condition     = alltrue([for ad in var.uygulamalar : can(regex("^[a-z][a-z0-9-]{1,40}$", ad))])
    error_message = "Uygulama adi kucuk harf, rakam ve tire olmali (namespace adi olarak kullanilir)."
  }
}

variable "gitops_repo" {
  description = "Kumede ne calisacagini tutan GitOps reposu (SSH; salt okunur deploy key ile)."
  type        = string
  default     = "git@github.com:AdanedhelWrites/yerel-gitops.git"
}

variable "uygulama_repolari" {
  description = "Uygulama chart'larinin okundugu repolar (kisisel projesi)."
  type        = list(string)
  default     = ["https://github.com/AdanedhelWrites/tech-radar.git"]
}
```

- [ ] **Step 5: `terraform/yapilandirma/vault.tf`**

```hcl
# Vault adresi ve token'i ortamdan gelir (VAULT_ADDR, VAULT_TOKEN; scripts/tf.sh).
provider "vault" {}

# Her istek ve yanit vault-0'in stdout'una yazilir: kubectl --context docker-desktop -n vault logs vault-0
resource "vault_audit" "stdout" {
  type = "file"
  path = "stdout"

  options = {
    file_path = "stdout"
  }
}

resource "vault_mount" "kv" {
  path        = "kv"
  type        = "kv"
  description = "Uygulama sirlari (KV v2): kv/<uygulama>/..., kv/argocd/..."

  options = {
    version = "2"
  }
}

# Vault kume icinde calisir; TokenReview'u kendi ServiceAccount'uyla yapar
# (vault chart'i system:auth-delegator baglamasini kurar).
resource "vault_auth_backend" "kubernetes" {
  type = "kubernetes"
  path = "kubernetes"
}

resource "vault_kubernetes_auth_backend_config" "kume" {
  backend         = vault_auth_backend.kubernetes.path
  kubernetes_host = "https://kubernetes.default.svc"
}

# En az yetki: uygulama yalniz kendi yolunu okur; rol yalniz kendi namespace'indeki
# <ad>-vso ServiceAccount'una verilir (uygulama pod'unun kendi kimligi Vault'a erisemez).
resource "vault_policy" "uygulama" {
  for_each = toset(var.uygulamalar)

  name   = each.key
  policy = <<-EOT
    path "kv/data/${each.key}/*" {
      capabilities = ["read"]
    }
  EOT
}

resource "vault_kubernetes_auth_backend_role" "uygulama" {
  for_each = toset(var.uygulamalar)

  backend                          = vault_auth_backend.kubernetes.path
  role_name                        = each.key
  bound_service_account_names      = ["${each.key}-vso"]
  bound_service_account_namespaces = [each.key]
  audience                         = "vault"
  token_policies                   = [vault_policy.uygulama[each.key].name]
  token_ttl                        = 3600
}

# Argo CD'nin GitOps reposu deploy key'i (scripts/repo_anahtari.sh yazar)
resource "vault_policy" "argocd_repo" {
  name   = "argocd-repo"
  policy = <<-EOT
    path "kv/data/argocd/*" {
      capabilities = ["read"]
    }
  EOT
}

resource "vault_kubernetes_auth_backend_role" "argocd_repo" {
  backend                          = vault_auth_backend.kubernetes.path
  role_name                        = "argocd-repo"
  bound_service_account_names      = ["argocd-vso"]
  bound_service_account_namespaces = ["argocd"]
  audience                         = "vault"
  token_policies                   = [vault_policy.argocd_repo.name]
  token_ttl                        = 3600
}
```

- [ ] **Step 6: `terraform/yapilandirma/argocd.tf`**

```hcl
provider "kubernetes" {
  config_path    = var.kubeconfig
  config_context = var.kube_context
}

locals {
  kume_ici = "https://kubernetes.default.svc"
}

# --- GitOps reposu erisimi: deploy key Vault'ta, Secret'i VSO yazar ---------------------

resource "kubernetes_service_account_v1" "argocd_vso" {
  metadata {
    name      = "argocd-vso"
    namespace = "argocd"
  }
}

resource "kubernetes_manifest" "argocd_vaultauth" {
  manifest = {
    apiVersion = "secrets.hashicorp.com/v1beta1"
    kind       = "VaultAuth"
    metadata = {
      name      = "argocd-vso"
      namespace = "argocd"
    }
    spec = {
      method = "kubernetes"
      mount  = vault_auth_backend.kubernetes.path
      kubernetes = {
        role           = vault_kubernetes_auth_backend_role.argocd_repo.role_name
        serviceAccount = kubernetes_service_account_v1.argocd_vso.metadata[0].name
        audiences      = ["vault"]
      }
    }
  }
}

# kv/argocd/yerel-gitops {type, url, sshPrivateKey} -> Argo CD repository Secret'i
resource "kubernetes_manifest" "gitops_repo_sirri" {
  manifest = {
    apiVersion = "secrets.hashicorp.com/v1beta1"
    kind       = "VaultStaticSecret"
    metadata = {
      name      = "yerel-gitops-repo"
      namespace = "argocd"
    }
    spec = {
      vaultAuthRef = kubernetes_manifest.argocd_vaultauth.manifest.metadata.name
      type         = "kv-v2"
      mount        = vault_mount.kv.path
      path         = "argocd/yerel-gitops"
      refreshAfter = "1h"
      destination = {
        name   = "repo-yerel-gitops"
        create = true
        labels = {
          "argocd.argoproj.io/secret-type" = "repository"
        }
        transformation = {
          excludeRaw = true
        }
      }
    }
  }
}

# --- Projeler ------------------------------------------------------------------------

# Kok uygulama: yalniz yerel-gitops'tan okur, yalniz argocd namespace'ine Application yazar.
resource "kubernetes_manifest" "proje_platform" {
  manifest = {
    apiVersion = "argoproj.io/v1alpha1"
    kind       = "AppProject"
    metadata = {
      name      = "platform"
      namespace = "argocd"
    }
    spec = {
      description = "Kok uygulama (yerel-gitops/apps): yalniz Application nesneleri"
      sourceRepos = [var.gitops_repo]
      destinations = [{
        server    = local.kume_ici
        namespace = "argocd"
      }]
      namespaceResourceWhitelist = [{
        group = "argoproj.io"
        kind  = "Application"
      }]
    }
  }
}

# Kisisel uygulamalar: chart'lar uygulama repolarindan, degerler/manifestler yerel-gitops'tan.
resource "kubernetes_manifest" "proje_kisisel" {
  manifest = {
    apiVersion = "argoproj.io/v1alpha1"
    kind       = "AppProject"
    metadata = {
      name      = "kisisel"
      namespace = "argocd"
    }
    spec = {
      description = "Kisisel uygulamalar (yerel deneme ortami)"
      sourceRepos = concat([var.gitops_repo], var.uygulama_repolari)
      destinations = [for ad in var.uygulamalar : {
        server    = local.kume_ici
        namespace = ad
      }]
      # CreateNamespace=true icin; baska kume kaynagi yok
      clusterResourceWhitelist = [{
        group = ""
        kind  = "Namespace"
      }]
    }
  }
}

# --- Kok Application ("app of apps") ---------------------------------------------------

resource "kubernetes_manifest" "kok" {
  manifest = {
    apiVersion = "argoproj.io/v1alpha1"
    kind       = "Application"
    metadata = {
      name      = "kok"
      namespace = "argocd"
      # Silinince alt Application'lar (ve onlarin kaynaklari) da silinir
      finalizers = ["resources-finalizer.argocd.argoproj.io"]
    }
    spec = {
      project = kubernetes_manifest.proje_platform.manifest.metadata.name
      source = {
        repoURL        = var.gitops_repo
        targetRevision = "main"
        path           = "apps"
      }
      destination = {
        server    = local.kume_ici
        namespace = "argocd"
      }
      syncPolicy = {
        automated = {
          prune    = true
          selfHeal = true
        }
      }
    }
  }

  depends_on = [kubernetes_manifest.proje_kisisel, kubernetes_manifest.gitops_repo_sirri]
}
```

- [ ] **Step 7: init, kilit, fmt, validate, test, birim testleri**

```bash
scripts/tf.sh yapilandirma init -input=false -upgrade >/dev/null
scripts/tf.sh yapilandirma providers lock -platform=windows_amd64 -platform=linux_amd64 | grep -E '^Success!'
grep -cE '^provider ' terraform/yapilandirma/.terraform.lock.hcl
scripts/tf.sh yapilandirma fmt -check -recursive && echo fmt-ok
scripts/tf.sh yapilandirma validate -no-color
scripts/tf.sh yapilandirma test -no-color | tail -1
bash tests/tf_koruma_test.sh | tail -2
```

Expected: `Success! Terraform has updated the lock file.` (ya da `...validated the lock file...`); `2`; `fmt-ok`; `Success! The configuration is valid.`; `Success! 1 passed, 0 failed.`; `ok    yapilandirma test (Vault gerekmez)` ve `TUM TESTLER GECTI`.

- [ ] **Step 8: Mutasyon kontrolu**

```bash
cp terraform/yapilandirma/variables.tf /tmp/v.yedek
sed -i 's/condition     = var.kube_context == "docker-desktop"/condition     = length(var.kube_context) > 0/' terraform/yapilandirma/variables.tf
scripts/tf.sh yapilandirma test -no-color 2>&1 | grep -cE 'Missing expected failure'
cp /tmp/v.yedek terraform/yapilandirma/variables.tf
scripts/tf.sh yapilandirma test -no-color | tail -1
```

Expected: `1`; geri alininca `Success! 1 passed, 0 failed.`

- [ ] **Step 9: Commit**

```bash
git add terraform/yapilandirma
git commit -m "feat: terraform yapilandirma asamasi (Vault auth/KV/audit, projeler, kok Application)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Operasyon betikleri (Vault, sirlar, deploy key, arayuz, yedek)

**Files:**
- Create: `scripts/vault_baslat.sh`, `scripts/vault_kilit_ac.sh`, `scripts/vault_yedek.sh`, `scripts/sir_yaz.sh`, `scripts/repo_anahtari.sh`, `scripts/arayuz.sh`

**Interfaces:**
- Consumes: `scripts/ortak.sh` (Task 1)
- Produces:
  - `scripts/vault_baslat.sh` — bir kez; `.vault/init.json` (`keys`, `keys_base64`, `root_token`) + unseal.
  - `scripts/vault_kilit_ac.sh` — unseal + `vault-0` Ready bekler.
  - `scripts/vault_yedek.sh` — `yedekler/vault-<zaman>.snap`.
  - `scripts/sir_yaz.sh <ad>` — `.sirlar/<ad>.env` -> `kv/<ad>/uygulama`; cikti `yazildi: kv/<ad>/uygulama (N anahtar, surum V)`.
  - `scripts/repo_anahtari.sh <sahip/repo>` — `kv/argocd/<repo>` {type, url, sshPrivateKey}; GitHub deploy key basligi `argocd-yerel`, salt okunur.
  - `scripts/arayuz.sh argocd|vault`.

Bu betiklerin davranisi gercek kume ister; dogrulamalari Task 8-12'dedir. Bu gorevin kapisi sozdizimi + shellcheck + mevcut testlerdir.

- [ ] **Step 1: `scripts/vault_baslat.sh`**

```bash
#!/usr/bin/env bash
# Vault'u BIR KEZ baslatir (spec 5.2): init (1 anahtar, esik 1) + unseal.
# Anahtar ve kok token .vault/init.json'a yazilir: git disi, yalniz bu kullanici okur,
# ekrana basilmaz. Docker Desktop yeniden baslayinca: scripts/vault_kilit_ac.sh
#
#   scripts/vault_baslat.sh
set -euo pipefail
. "$(dirname "$0")/ortak.sh"

baglam_dogrula
[ -e "$VAULT_INIT" ] && kaldi "$VAULT_INIT zaten var: Vault baslatilmis. Kilit icin: scripts/vault_kilit_ac.sh"

# vault-0 Running olmali (unseal'a kadar Ready olmaz)
for _ in $(seq 1 60); do
  [ "$(k get pod vault-0 -n vault -o jsonpath='{.status.phase}' 2>/dev/null)" = Running ] && break
  sleep 5
done
[ "$(k get pod vault-0 -n vault -o jsonpath='{.status.phase}')" = Running ] \
  || kaldi "vault-0 Running degil (once: scripts/tf.sh kume apply)"

vault_baglan
durum=$(curl -s "$VAULT_ADRES/v1/sys/seal-status")
[ "$(echo "$durum" | jq -r .initialized)" = false ] \
  || kaldi "Vault baslatilmis ama $VAULT_INIT yok: anahtarlar kayip. Sokup yeniden kurun (README)."

mkdir -p "$VAULT_DIZIN"
yalniz_bana "$VAULT_DIZIN"
kod=$(curl -s -X PUT -o "$VAULT_INIT.yeni" -w '%{http_code}' \
  --data-binary '{"secret_shares":1,"secret_threshold":1}' "$VAULT_ADRES/v1/sys/init")
[ "$kod" = 200 ] || { rm -f "$VAULT_INIT.yeni"; kaldi "init HTTP $kod"; }
jq -e '(.keys_base64 | length) == 1 and (.root_token | length) > 0' "$VAULT_INIT.yeni" >/dev/null \
  || { rm -f "$VAULT_INIT.yeni"; kaldi "init yaniti beklenen bicimde degil"; }
mv "$VAULT_INIT.yeni" "$VAULT_INIT"
yalniz_bana "$VAULT_INIT"
echo "Vault baslatildi; anahtar ve kok token: $VAULT_INIT (yalniz bu kullanici)"

vault_kilidi_ac
echo "Vault kilidi acik. Siradaki: scripts/tf.sh yapilandirma init && scripts/tf.sh yapilandirma apply"
```

- [ ] **Step 2: `scripts/vault_kilit_ac.sh`**

```bash
#!/usr/bin/env bash
# Vault'un kilidini .vault/init.json'daki anahtarla acar (spec 5.2). Docker Desktop ya da
# vault-0 yeniden baslayinca calistirin. Kilitliyken uygulamalar calisir (VSO'nun yazdigi
# Secret'lar durur); yalniz sir yenilemesi bekler.
#
#   scripts/vault_kilit_ac.sh
set -euo pipefail
. "$(dirname "$0")/ortak.sh"

baglam_dogrula
for _ in $(seq 1 60); do
  [ "$(k get pod vault-0 -n vault -o jsonpath='{.status.phase}' 2>/dev/null)" = Running ] && break
  sleep 5
done
vault_baglan
vault_kilidi_ac
k wait --for=condition=Ready pod/vault-0 -n vault --timeout=120s >/dev/null || kaldi "vault-0 Ready olmadi"
echo "Vault kilidi acik; vault-0 Ready."
```

- [ ] **Step 3: `scripts/vault_yedek.sh`**

```bash
#!/usr/bin/env bash
# Vault Raft snapshot'i alir (spec 7: platform yukseltmeden once).
#   scripts/vault_yedek.sh   ->  yedekler/vault-<zaman>.snap  (git disi, yalniz bu kullanici)
# Geri yukleme ayni unseal anahtarini ister (.vault/init.json).
set -euo pipefail
. "$(dirname "$0")/ortak.sh"

baglam_dogrula
vault_baglan
vault_muhurlu_mu && kaldi "Vault kilitli: once scripts/vault_kilit_ac.sh"
vault_kok_token_yukle

mkdir -p "$KOK/yedekler"
yalniz_bana "$KOK/yedekler"
hedef="$KOK/yedekler/vault-$(date +%Y%m%d-%H%M%S).snap"
kod=$(printf 'header = "X-Vault-Token: %s"\n' "$VAULT_ISTEK_TOKEN" \
  | curl -s -K - -o "$hedef" -w '%{http_code}' "$VAULT_ADRES/v1/sys/storage/raft/snapshot")
[ "$kod" = 200 ] && [ -s "$hedef" ] || { rm -f "$hedef"; kaldi "snapshot HTTP $kod"; }
echo "Vault snapshot: $hedef ($(wc -c < "$hedef") bayt)"
```

- [ ] **Step 4: `scripts/sir_yaz.sh`**

```bash
#!/usr/bin/env bash
# Bir uygulamanin sirlarini git disi yerel dosyadan Vault'a yazar (spec 5.4):
#   .sirlar/<ad>.env  ->  kv/<ad>/uygulama   (KV v2; her yazma yeni surum)
#
#   scripts/sir_yaz.sh <ad>
#
# Dosya bicimi: ANAHTAR=deger satirlari (tirnaksiz). Dosya yalniz bu kullanicinin
# okuyabilecegi sekilde kisitlanir. Degerler ekrana, komut satirina ve Terraform'a girmez.
# VSO degisikligi en gec refreshAfter (1h) icinde tasir; hemen icin README "Sir rotasyonu".
set -euo pipefail
. "$(dirname "$0")/ortak.sh"

ad="${1:-}"
[[ "$ad" =~ ^[a-z][a-z0-9-]{1,40}$ ]] || { echo "kullanim: $0 <ad>   (ornek: tech-radar)" >&2; exit 2; }
dosya="$SIR_DIZIN/$ad.env"
[ -f "$dosya" ] || kaldi "$dosya yok (ornek: README 'Sirlar')"

yalniz_bana "$SIR_DIZIN"
yalniz_bana "$dosya"
env_json "$dosya" > "$GECICI/govde.json"
sayi=$(jq '.data | length' "$GECICI/govde.json")

baglam_dogrula
vault_baglan
vault_muhurlu_mu && kaldi "Vault kilitli: once scripts/vault_kilit_ac.sh"
vault_kok_token_yukle
kod=$(vault_istek POST "kv/data/$ad/uygulama" "$GECICI/govde.json")
rm -f "$GECICI/govde.json"
[ "$kod" = 200 ] || kaldi "Vault yazma HTTP $kod (kv/$ad/uygulama)"
echo "yazildi: kv/$ad/uygulama ($sayi anahtar, surum $(jq -r .data.version "$GECICI/yanit.json"))"
```

- [ ] **Step 5: `scripts/repo_anahtari.sh`**

```bash
#!/usr/bin/env bash
# Argo CD icin GitOps reposuna SALT OKUNUR deploy key kurar ya da yeniler (spec 5.4).
#   - ed25519 anahtar gecici dizinde uretilir;
#   - ozel yarisi Vault'a yazilir: kv/argocd/<repo-adi> {type, url, sshPrivateKey}
#     (VSO bunu argocd namespace'inde repository Secret'ina cevirir);
#   - ayni basliktaki eski deploy key'ler GitHub'dan silinir, acik yarisi eklenir
#     (--allow-write YOK: salt okunur);
#   - gecici dizin betik bitince silinir. Anahtar ekrana basilmaz.
# DISARIYA DONUK: GitHub'da deploy key ekler/siler. Kullanici onayiyla calistirin.
#
#   scripts/repo_anahtari.sh AdanedhelWrites/yerel-gitops
set -euo pipefail
. "$(dirname "$0")/ortak.sh"

repo="${1:-}"
[[ "$repo" =~ ^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$ ]] || { echo "kullanim: $0 <sahip/repo>" >&2; exit 2; }
ad="${repo#*/}"
BASLIK=argocd-yerel

gh repo view "$repo" --json name -q .name >/dev/null || kaldi "GitHub reposu yok ya da erisilemiyor: $repo"
baglam_dogrula
vault_baglan
vault_muhurlu_mu && kaldi "Vault kilitli: once scripts/vault_kilit_ac.sh"
vault_kok_token_yukle

ssh-keygen -q -t ed25519 -N "" -C "$BASLIK@$ad" -f "$GECICI/anahtar"
jq -n --rawfile k "$GECICI/anahtar" --arg url "git@github.com:$repo.git" \
  '{data: {type: "git", url: $url, sshPrivateKey: $k}}' > "$GECICI/govde.json"
rm -f "$GECICI/anahtar"
kod=$(vault_istek POST "kv/data/argocd/$ad" "$GECICI/govde.json")
rm -f "$GECICI/govde.json"
[ "$kod" = 200 ] || kaldi "Vault yazma HTTP $kod (kv/argocd/$ad)"
echo "ozel anahtar Vault'ta: kv/argocd/$ad"

for id in $(gh api "repos/$repo/keys" --jq ".[] | select(.title == \"$BASLIK\") | .id"); do
  gh api -X DELETE "repos/$repo/keys/$id" >/dev/null
  echo "eski deploy key silindi (id $id)"
done
gh repo deploy-key add "$GECICI/anahtar.pub" --repo "$repo" --title "$BASLIK" >/dev/null
salt_okunur=$(gh api "repos/$repo/keys" --jq "[.[] | select(.title == \"$BASLIK\")] | length == 1 and all(.read_only)")
[ "$salt_okunur" = true ] || kaldi "deploy key salt okunur degil ya da birden fazla"
echo "deploy key eklendi: $repo ($BASLIK, read_only)"
```

- [ ] **Step 6: `scripts/arayuz.sh`**

```bash
#!/usr/bin/env bash
# Argo CD ya da Vault arayuzunu yalniz 127.0.0.1'de acar (port-forward; Ctrl+C kapatir).
#
#   scripts/arayuz.sh argocd   # http://127.0.0.1:8080  kullanici admin; ilk parola panoya
#   scripts/arayuz.sh vault    # http://127.0.0.1:8200  kok token panoya
#
# Parola/token ekrana basilmaz; clip.exe ile panoya kopyalanir.
set -euo pipefail
. "$(dirname "$0")/ortak.sh"

baglam_dogrula
case "${1:-}" in
  argocd)
    if k get secret argocd-initial-admin-secret -n argocd >/dev/null 2>&1; then
      k get secret argocd-initial-admin-secret -n argocd -o jsonpath='{.data.password}' \
        | base64 -d | clip.exe
      echo "Ilk admin parolasi panoda. Giristen sonra: User Info -> Update Password, sonra:"
      echo "  kubectl --context $BAGLAM -n argocd delete secret argocd-initial-admin-secret"
    else
      echo "argocd-initial-admin-secret yok (parola degistirilmis). Kullanici: admin"
    fi
    echo "Argo CD: http://127.0.0.1:8080   (kapatmak: Ctrl+C)"
    kubectl --context "$BAGLAM" port-forward -n argocd svc/argocd-server 8080:80
    ;;
  vault)
    vault_kok_token_yukle
    printf '%s' "$VAULT_ISTEK_TOKEN" | clip.exe
    echo "Kok token panoda (Method: Token). Vault: http://127.0.0.1:8200/ui   (kapatmak: Ctrl+C)"
    kubectl --context "$BAGLAM" port-forward -n vault pod/vault-0 "$VAULT_PORT:8200"
    ;;
  *) echo "kullanim: $0 argocd|vault" >&2; exit 2 ;;
esac
```

- [ ] **Step 7: Sozdizimi, shellcheck, testler**

```bash
for f in scripts/*.sh; do bash -n "$f" || echo "SOZDIZIMI HATASI: $f"; done
MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W):/mnt" -w /mnt \
  koalaman/shellcheck:v0.11.0@sha256:61862eba1fcf09a484ebcc6feea46f1782532571a34ed51fedf90dd25f925a8d \
  -x -S warning scripts/*.sh tests/*.sh && echo shellcheck-temiz
bash tests/tf_koruma_test.sh | tail -1
grep -nE 'echo .*(root_token|VAULT_ISTEK_TOKEN|sshPrivateKey)|set -x' scripts/*.sh || echo "sir basan satir yok"
```

Expected: hata satiri yok; `shellcheck-temiz`; `TUM TESTLER GECTI`; `sir basan satir yok`.

- [ ] **Step 8: Commit**

```bash
git add --chmod=+x scripts/vault_baslat.sh scripts/vault_kilit_ac.sh scripts/vault_yedek.sh scripts/sir_yaz.sh scripts/repo_anahtari.sh scripts/arayuz.sh
git commit -m "feat: Vault baslatma/kilit/yedek, sir yazma, deploy key ve arayuz betikleri

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Dogrulama betigi `scripts/k8s_dogrulama.sh` (T1-T5, T11)

**Files:**
- Create: `scripts/k8s_dogrulama.sh`

**Interfaces:**
- Consumes: `scripts/ortak.sh`, `scripts/tf.sh`, `scripts/vault_kilit_ac.sh`, Task 2-3 kaynak adlari
- Produces: `scripts/k8s_dogrulama.sh b3a | t1 t2 t3 t4 t5 t11`. Yardimcilar (B3b genisletir): `ready_olmayanlar <ns>`, `hepsi_ready_bekle <ns> <sn>`, `vault_hazir`, `vss_durumu <ns> <ad>`, `vss_tetikle <ns> <ad>`, `vss_bekle <ns> <ad> <True|False> <sn>`, `plan_degisiksiz <asama>`, `uygulama_saglik` (-> `SAGLIK_KODU`), `kubernetes_giris <ns> <rol>`; sabitler `GITOPS_REPO=AdanedhelWrites/yerel-gitops`, `DEPLOY_KEY_BASLIGI=argocd-yerel`, `API_PORT=18000`. B3b, `# --- giris noktasi` satirindan once T6-T10, T12 ekler.

- [ ] **Step 1: `scripts/k8s_dogrulama.sh`**

```bash
#!/usr/bin/env bash
# B3 kume dogrulamasi (spec 8) - YALNIZ yerel docker-desktop kumesinde.
# Her senaryo GECTI/KALDI basar; ilk hatada durur. Sir degerleri basilmaz.
#
#   scripts/k8s_dogrulama.sh b3a              # T1-T5, T11 (B3a kapisi)
#   scripts/k8s_dogrulama.sh t1 t3 ...        # tek tek senaryolar
set -euo pipefail
. "$(dirname "$0")/ortak.sh"

GITOPS_REPO=AdanedhelWrites/yerel-gitops
DEPLOY_KEY_BASLIGI=argocd-yerel
API_PORT=18000

# --- yardimcilar ------------------------------------------------------------------------

ready_olmayanlar() {   # ready_olmayanlar <namespace> -> Ready olmayan (Succeeded disi) pod'lar
  k get pods -n "$1" --field-selector=status.phase!=Succeeded \
    -o jsonpath='{range .items[*]}{.metadata.name}{" "}{range .status.conditions[?(@.type=="Ready")]}{.status}{end}{"\n"}{end}' \
    | awk '$2 != "True" {print $1}'
}

hepsi_ready_bekle() {   # hepsi_ready_bekle <namespace> <saniye>
  local ns=$1 sure=$2 kalan="" _
  for _ in $(seq 1 $((sure / 5))); do
    kalan=$(ready_olmayanlar "$ns")
    [ -z "$kalan" ] && [ -n "$(k get pods -n "$ns" -o name)" ] && return 0
    sleep 5
  done
  kaldi "$ns: Ready olmayan pod: ${kalan:-pod yok}"
}

vault_hazir() {   # port-forward + kilit acik + kok token
  vault_baglan
  vault_muhurlu_mu && kaldi "Vault kilitli: once scripts/vault_kilit_ac.sh"
  vault_kok_token_yukle
}

vss_durumu() {   # vss_durumu <namespace> <ad> -> SecretSynced kosulunun durumu (True/False/"")
  k get vaultstaticsecret "$2" -n "$1" -o jsonpath='{.status.conditions[?(@.type=="SecretSynced")].status}'
}

vss_tetikle() {   # VSO'yu hemen okumaya zorlar: annotation degisikligi reconcile baslatir
  k annotate vaultstaticsecret "$2" -n "$1" "yerel-platform/yenile=$(date +%s%N)" --overwrite >/dev/null
}

vss_bekle() {   # vss_bekle <namespace> <ad> <True|False> <saniye>
  local _
  for _ in $(seq 1 $(($4 / 3))); do
    [ "$(vss_durumu "$1" "$2")" = "$3" ] && return 0
    sleep 3
  done
  return 1
}

plan_degisiksiz() {   # plan_degisiksiz <asama> -> 0: "No changes"
  local rc=0
  "$KOK/scripts/tf.sh" "$1" plan -detailed-exitcode -input=false -no-color > "$GECICI/plan-$1.txt" 2>&1 || rc=$?
  case "$rc" in
    0) return 0 ;;
    2) grep -E '^  # |Plan:' "$GECICI/plan-$1.txt" >&2; return 1 ;;
    *) tail -20 "$GECICI/plan-$1.txt" >&2; kaldi "$1 plan hata verdi (rc $rc)" ;;
  esac
}

# tech-radar backend /api/v1/health/ kodunu SAGLIK_KODU'na yazar. $(...) icinde CAGIRMAYIN:
# port-forward'un PID'i alt kabukta kalir ve kubectl.exe acik kalir.
# URL localhost: ALLOWED_HOSTS 127.0.0.1 icermez (Host: 127.0.0.1 -> 400).
SAGLIK_KODU=""
uygulama_saglik() {
  local _
  SAGLIK_KODU=000
  [ -n "${API_PF_ACIK:-}" ] || { pf_ac tech-radar svc/teknoloji-api "$API_PORT:8000"; API_PF_ACIK=1; }
  for _ in $(seq 1 20); do
    SAGLIK_KODU=$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "http://localhost:$API_PORT/api/v1/health/" || true)
    [ "$SAGLIK_KODU" = 200 ] && return 0
    sleep 1
  done
}

# --- senaryolar -------------------------------------------------------------------------

t1() {
  hepsi_ready_bekle argocd 600
  hepsi_ready_bekle vault-secrets-operator 300
  hepsi_ready_bekle vault 300
  plan_degisiksiz kume || kaldi "T1 ikinci 'tf.sh kume plan' degisiklik gosteriyor"
  gecti "T1 platform: argocd, vault, vault-secrets-operator pod'lari Ready; kume plan: No changes"
}

t2() {
  vault_baglan
  local durum
  durum=$(curl -s "$VAULT_ADRES/v1/sys/seal-status")
  [ "$(echo "$durum" | jq -r .initialized)" = true ] || kaldi "T2 Vault baslatilmamis"
  [ "$(echo "$durum" | jq -r .sealed)" = false ] || kaldi "T2 Vault kilitli"
  yalniz_bende_mi "$VAULT_INIT" || kaldi "T2 $VAULT_INIT yalniz bu kullaniciya ait degil"
  git -C "$KOK" check-ignore -q .vault/init.json || kaldi "T2 .vault/init.json git-ignore degil"
  git -C "$KOK" check-ignore -q .sirlar/tech-radar.env || kaldi "T2 .sirlar/ git-ignore degil"
  gecti "T2 Vault: initialized, sealed=false; init.json yalniz bu kullanicida ve git disi"
}

t3() {
  plan_degisiksiz yapilandirma || kaldi "T3 ikinci 'tf.sh yapilandirma plan' degisiklik gosteriyor"
  # State'te sir olmamali: kok token, unseal anahtari, .sirlar degerleri, ozel anahtar
  ( jq -r '.root_token, .keys_base64[], .keys[]' "$VAULT_INIT"
    for f in "$SIR_DIZIN"/*.env; do
      [ -f "$f" ] && env_json "$f" | jq -r '.data[] | select(length >= 8)'
    done
    echo "PRIVATE KEY" ) | sed '/^$/d' > "$GECICI/desenler"
  local asama
  for asama in kume yapilandirma; do
    "$KOK/scripts/tf.sh" "$asama" state pull > "$GECICI/durum-$asama.json"
    [ -s "$GECICI/durum-$asama.json" ] || kaldi "T3 $asama state bos"
    if grep -F -q -f "$GECICI/desenler" "$GECICI/durum-$asama.json"; then
      kaldi "T3 $asama state'inde sir degeri var"
    fi
  done
  local istek
  istek=$(k logs -n vault vault-0 --since=1h | grep -c '"type":"request"' || true)
  [ "$istek" -ge 1 ] || kaldi "T3 audit kaydi yok (vault-0 stdout)"
  gecti "T3 yapilandirma: plan No changes; kume/yapilandirma state'lerinde sir yok; audit $istek istek"
}

kubernetes_giris() {   # kubernetes_giris <namespace> <rol> -> HTTP kodu; yanit GECICI/yanit.json
  k create token tech-radar-vso -n "$1" --audience vault --duration 10m \
    | jq -Rn --arg r "$2" '{role: $r, jwt: input}' > "$GECICI/giris.json"
  local kok_token=$VAULT_ISTEK_TOKEN kod
  VAULT_ISTEK_TOKEN=""
  kod=$(vault_istek POST auth/kubernetes/login "$GECICI/giris.json")
  VAULT_ISTEK_TOKEN=$kok_token
  rm -f "$GECICI/giris.json"
  echo "$kod"
}

t4() {
  vault_hazir
  [ "$(vault_istek GET kv/data/tech-radar/uygulama)" = 200 ] \
    || kaldi "T4 kv/tech-radar/uygulama yok (once: scripts/sir_yaz.sh tech-radar)"
  local olusan_ns="" olusan_sa="" kod kok_token rol_token
  k get ns tech-radar >/dev/null 2>&1 || { k create ns tech-radar >/dev/null; olusan_ns=1; }
  k get sa tech-radar-vso -n tech-radar >/dev/null 2>&1 || { k create sa tech-radar-vso -n tech-radar >/dev/null; olusan_sa=1; }
  k delete ns t4-baska --ignore-not-found --wait=true >/dev/null
  k create ns t4-baska >/dev/null
  k create sa tech-radar-vso -n t4-baska >/dev/null

  kod=$(kubernetes_giris tech-radar tech-radar)
  [ "$kod" = 200 ] || kaldi "T4 tech-radar/tech-radar-vso girisi HTTP $kod"
  rol_token=$(jq -r .auth.client_token "$GECICI/yanit.json")
  kok_token=$VAULT_ISTEK_TOKEN
  VAULT_ISTEK_TOKEN=$rol_token
  kod=$(vault_istek GET kv/data/tech-radar/uygulama)
  [ "$kod" = 200 ] || kaldi "T4 rol kendi sirrini okuyamadi (HTTP $kod)"
  kod=$(vault_istek GET kv/data/argocd/yerel-gitops)
  [ "$kod" = 403 ] || kaldi "T4 rol kv/argocd'u okuyabildi ya da beklenmeyen kod (HTTP $kod)"
  vault_istek POST auth/token/revoke-self >/dev/null
  VAULT_ISTEK_TOKEN=$kok_token

  kod=$(kubernetes_giris t4-baska tech-radar)
  case "$kod" in 400|403) ;; *) kaldi "T4 baska namespace'ten giris reddedilmedi (HTTP $kod)" ;; esac
  [ "$(jq -r '.auth.client_token // empty' "$GECICI/yanit.json")" = "" ] || kaldi "T4 baska namespace token aldi"

  k delete ns t4-baska --wait=false >/dev/null
  [ -n "$olusan_sa" ] && k delete sa tech-radar-vso -n tech-radar >/dev/null
  [ -n "$olusan_ns" ] && k delete ns tech-radar --wait=false >/dev/null
  gecti "T4 en az yetki: tech-radar rolu kv/tech-radar okur (200), kv/argocd okuyamaz (403); t4-baska girisi reddedildi ($kod)"
}

t5() {
  local salt_okunur durum rev beklenen _
  salt_okunur=$(gh api "repos/$GITOPS_REPO/keys" --jq "[.[] | select(.title == \"$DEPLOY_KEY_BASLIGI\")] | length == 1 and all(.read_only)")
  [ "$salt_okunur" = true ] || kaldi "T5 GitHub'da tek ve salt okunur '$DEPLOY_KEY_BASLIGI' deploy key yok"
  [ "$(k get secret repo-yerel-gitops -n argocd -o jsonpath='{.metadata.labels.argocd\.argoproj\.io/secret-type}')" = repository ] \
    || kaldi "T5 repo-yerel-gitops Secret'i yok ya da repository etiketi yok"
  [ "$(vss_durumu argocd yerel-gitops-repo)" = True ] || kaldi "T5 VaultStaticSecret yerel-gitops-repo SecretSynced degil"
  beklenen=$(gh api "repos/$GITOPS_REPO/commits/main" --jq .sha)
  k annotate application kok -n argocd argocd.argoproj.io/refresh=hard --overwrite >/dev/null
  for _ in $(seq 1 60); do
    durum=$(k get application kok -n argocd -o jsonpath='{.status.sync.status}')
    rev=$(k get application kok -n argocd -o jsonpath='{.status.sync.revision}')
    [ "$durum" = Synced ] && [ "$rev" = "$beklenen" ] && break
    sleep 5
  done
  [ "$durum" = Synced ] && [ "$rev" = "$beklenen" ] \
    || kaldi "T5 kok Application: durum=$durum revizyon=$rev (beklenen Synced @ $beklenen); $(k get application kok -n argocd -o jsonpath='{.status.conditions[*].message}')"
  gecti "T5 repo erisimi: deploy key read_only; Secret VSO'dan; kok Application Synced @ ${rev:0:7}"
}

t11() {
  vault_hazir
  [ "$(vss_durumu argocd yerel-gitops-repo)" = True ] || kaldi "T11 on kosul: yerel-gitops-repo SecretSynced degil"
  local uygulama_var="" _
  k get application tech-radar -n argocd >/dev/null 2>&1 && uygulama_var=1

  k delete pod vault-0 -n vault --wait=true >/dev/null
  for _ in $(seq 1 60); do
    [ "$(k get pod vault-0 -n vault -o jsonpath='{.status.phase}' 2>/dev/null)" = Running ] && break
    sleep 5
  done
  vault_baglan
  vault_muhurlu_mu || kaldi "T11 yeni vault-0 kilitli degil (Raft verisi kayboldu mu?)"

  k get secret repo-yerel-gitops -n argocd >/dev/null || kaldi "T11 kilitliyken repo Secret'i kayboldu"
  vss_tetikle argocd yerel-gitops-repo
  vss_bekle argocd yerel-gitops-repo False 60 || kaldi "T11 kilitliyken VSO okuma hatasi gormedi"
  [ "$(k get application kok -n argocd -o jsonpath='{.status.sync.status}')" = Synced ] \
    || kaldi "T11 kilitliyken kok Application Synced degil"
  if [ -n "$uygulama_var" ]; then
    uygulama_saglik
    [ "$SAGLIK_KODU" = 200 ] || kaldi "T11 kilitliyken tech-radar health $SAGLIK_KODU"
  fi

  "$KOK/scripts/vault_kilit_ac.sh" >/dev/null
  vault_baglan
  vss_tetikle argocd yerel-gitops-repo
  vss_bekle argocd yerel-gitops-repo True 90 || kaldi "T11 kilit acildiktan sonra VSO yenilemesi surmedi"
  gecti "T11 Vault yeniden baslatma: kilitliyken Secret ve kok Application yerinde${uygulama_var:+, tech-radar health 200}; kilit acilinca VSO yeniden okudu"
}

# --- giris noktasi ----------------------------------------------------------------------

baglam_dogrula
[ $# -ge 1 ] || { echo "kullanim: $0 b3a | t1 t2 t3 t4 t5 t11" >&2; exit 2; }
for senaryo in "$@"; do
  case "$senaryo" in
    b3a) t1; t2; t3; t4; t5; t11; echo "B3a KAPISI GECTI (T1-T5, T11)" ;;
    t1|t2|t3|t4|t5|t11) "$senaryo" ;;
    *) echo "bilinmeyen senaryo: $senaryo" >&2; exit 2 ;;
  esac
done
```

- [ ] **Step 2: Sozdizimi, shellcheck, kullanim**

```bash
bash -n scripts/k8s_dogrulama.sh
MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W):/mnt" -w /mnt \
  koalaman/shellcheck:v0.11.0@sha256:61862eba1fcf09a484ebcc6feea46f1782532571a34ed51fedf90dd25f925a8d \
  -x -S warning scripts/*.sh tests/*.sh && echo shellcheck-temiz
scripts/k8s_dogrulama.sh t99; echo "rc=$?"
```

Expected: `shellcheck-temiz`; `baglam yerel: docker-desktop (...)`, `bilinmeyen senaryo: t99`, `rc=2` (baglam dogrulamasi kumeye yalniz okuma yapar).

- [ ] **Step 3: Commit**

```bash
git add --chmod=+x scripts/k8s_dogrulama.sh
git commit -m "test: B3a kume dogrulama betigi (T1-T5, T11)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: CI ve README

**Files:**
- Create: `.github/workflows/ci.yml`
- Modify: `README.md` (sona bolum)

**Interfaces:**
- Consumes: Task 1-5
- Produces: GitHub Actions `CI` (isler `terraform`, `betikler`, `gitleaks`)

- [ ] **Step 1: `.github/workflows/ci.yml`**

```yaml
# yerel-platform CI (spec B3 9). Yerel kumeye ERISMEZ: yalniz statik kontroller.
# Kapi: terraform fmt/validate, betik testleri + shellcheck, gitleaks.

name: CI

on:
  push:
    branches: ["main"]
  pull_request:
    branches: ["main"]
  workflow_dispatch:

permissions: {}

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  terraform:
    name: Terraform (fmt + validate)
    runs-on: ubuntu-latest
    timeout-minutes: 10
    permissions:
      contents: read
    steps:
      - name: Harden runner
        uses: step-security/harden-runner@e14015d583714f6e62063499dc959a02595150a1 # v2.21.1
        with:
          egress-policy: audit

      - name: Checkout
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false

      - name: Terraform
        uses: hashicorp/setup-terraform@dfe3c3f87815947d99a8997f908cb6525fc44e9e # v4.0.1
        with:
          terraform_version: "1.16.4"
          terraform_wrapper: false

      - name: fmt
        run: terraform fmt -check -recursive -diff terraform

      - name: init + validate (backend yok, kumeye baglanmaz)
        run: |
          set -euo pipefail
          for asama in kume yapilandirma; do
            terraform -chdir="terraform/$asama" init -backend=false -input=false -lockfile=readonly
            terraform -chdir="terraform/$asama" validate
          done

  betikler:
    name: Betikler (testler + shellcheck)
    runs-on: ubuntu-latest
    timeout-minutes: 10
    permissions:
      contents: read
    steps:
      - name: Harden runner
        uses: step-security/harden-runner@e14015d583714f6e62063499dc959a02595150a1 # v2.21.1
        with:
          egress-policy: audit

      - name: Checkout
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false

      - name: Testler
        run: |
          set -euo pipefail
          bash tests/tf_koruma_test.sh
          bash tests/env_json_test.sh
          bash tests/izin_test.sh   # Windows disinda "atlandi"

      - name: shellcheck
        run: |
          docker run --rm -v "$PWD:/mnt" -w /mnt \
            koalaman/shellcheck:v0.11.0@sha256:61862eba1fcf09a484ebcc6feea46f1782532571a34ed51fedf90dd25f925a8d \
            -x -S warning scripts/*.sh tests/*.sh

  gitleaks:
    name: gitleaks (tum gecmis)
    runs-on: ubuntu-latest
    timeout-minutes: 10
    permissions:
      contents: read
    env:
      GITLEAKS_VERSION: "8.30.1"
      GITLEAKS_SHA256: "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb"
    steps:
      - name: Harden runner
        uses: step-security/harden-runner@e14015d583714f6e62063499dc959a02595150a1 # v2.21.1
        with:
          egress-policy: audit

      - name: Checkout (tum gecmis)
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0
          persist-credentials: false

      - name: gitleaks kur (sabit surum + SHA256)
        run: |
          set -euo pipefail
          tarball="gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz"
          curl -fsSL --retry 3 -o "${RUNNER_TEMP}/${tarball}" \
            "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/${tarball}"
          echo "${GITLEAKS_SHA256}  ${RUNNER_TEMP}/${tarball}" | sha256sum -c -
          tar -xzf "${RUNNER_TEMP}/${tarball}" -C "${RUNNER_TEMP}" gitleaks

      # Private repo: code scanning (SARIF) yok; her bulgu kirmizidir.
      - name: Tara
        run: |
          set -uo pipefail
          "${RUNNER_TEMP}/gitleaks" git . --redact --no-banner --no-color --exit-code 2 \
            --log-opts="--all" 2>&1 | tee gitleaks.log
          rc=${PIPESTATUS[0]}
          commits=$(grep -oE '[0-9]+ commits scanned' gitleaks.log | grep -oE '^[0-9]+' | tail -1)
          if [ -z "${commits}" ] || [ "${commits}" -lt 1 ]; then
            echo "::error::gitleaks hic commit taramadi"; exit 1
          fi
          if [ "${rc}" -eq 2 ]; then echo "::error::gitleaks sir buldu"; exit 1; fi
          if [ "${rc}" -ne 0 ]; then echo "::error::gitleaks arac hatasi (exit ${rc})"; exit 1; fi
          echo "### gitleaks: ${commits} commit, bulgu yok" >> "${GITHUB_STEP_SUMMARY}"
```

- [ ] **Step 2: `README.md`'nin sonuna ekle**

````markdown
## Kubernetes platformu: Argo CD + Vault + VSO (B3)

Yerel Docker Desktop Kubernetes'ine (`docker-desktop`) Terraform ile **Argo CD**, **HashiCorp
Vault** (tek dugum, Raft) ve **Vault Secrets Operator (VSO)** kurulur. Uygulamalar
`AdanedhelWrites/yerel-gitops` reposundan Argo CD ile gelir; sirlari Vault'tan VSO tasir.
Tasarim: tech-radar `docs/superpowers/specs/2026-10-03-b3-terraform-argocd-vault-design.md`,
ADR-0008.

**Kural:** Terraform yalniz `scripts/tf.sh` ile calisir; her `kubectl` `--context docker-desktop`
tasir. `kubectl config use-context` kullanmayin (aktif baglam baska bir kume olabilir). Her betik
baslangicta baglamin yerel oldugunu (sunucu `kubernetes.docker.internal`/`127.0.0.1`, dugum
`docker-desktop`) dogrular; degilse hicbir sey yapmaz.

### Gereksinimler

Terraform >= 1.16 (`winget install Hashicorp.Terraform`), Docker Desktop Kubernetes (kubeadm),
Docker Desktop bellegi >= 8 GB, `jq`, `gh` (deploy key icin, `gh auth login`).

| Bilesen | Surum (sabit) |
|---|---|
| Argo CD chart `argo-cd` | 10.9.6 (Argo CD v3.5.3) |
| Vault chart `vault` | 0.34.1 (Vault 2.0.4) |
| VSO chart `vault-secrets-operator` | 1.6.0 |
| Terraform provider'lari | helm 3.3.0, kubernetes 3.3.0, vault 5.12.0 (`.terraform.lock.hcl`) |

### Ilk kurulum (sira onemli)

```bash
scripts/tf.sh kume init && scripts/tf.sh kume apply                 # Argo CD, Vault, VSO
scripts/vault_baslat.sh                                              # BIR KEZ: .vault/init.json
scripts/tf.sh yapilandirma init && scripts/tf.sh yapilandirma apply  # Vault ayarlari, projeler, kok uygulama
scripts/sir_yaz.sh tech-radar                                        # .sirlar/tech-radar.env -> Vault
scripts/repo_anahtari.sh AdanedhelWrites/yerel-gitops                # salt okunur deploy key (GitHub'a yazar)
scripts/k8s_dogrulama.sh b3a                                         # T1-T5, T11
```

### Gunluk isler

| Is | Komut |
|---|---|
| Docker Desktop ya da `vault-0` yeniden basladi | `scripts/vault_kilit_ac.sh` |
| Argo CD arayuzu | `scripts/arayuz.sh argocd` -> http://127.0.0.1:8080 (admin; ilk parola panoda) |
| Vault arayuzu | `scripts/arayuz.sh vault` -> http://127.0.0.1:8200/ui (kok token panoda) |
| Sir degistirme | `.sirlar/<ad>.env`'i duzenle -> `scripts/sir_yaz.sh <ad>`; VSO en gec 1 saatte tasir. Hemen: `kubectl --context docker-desktop -n <ad> annotate vaultstaticsecret <secret-adi> yerel-platform/yenile="$(date +%s)" --overwrite` |
| Deploy key yenileme | `scripts/repo_anahtari.sh AdanedhelWrites/yerel-gitops` (eskisini GitHub'dan siler) |
| Platform yukseltme | `scripts/vault_yedek.sh` -> `terraform/kume/main.tf`'te chart surumu -> `scripts/tf.sh kume plan` -> `apply` |
| Yeni kisisel uygulama | `scripts/uygulama_ekle.sh <ad>` + `terraform/yapilandirma/variables.tf` `uygulamalar` + `scripts/tf.sh yapilandirma apply` + `.sirlar/<ad>.env` + `scripts/sir_yaz.sh <ad>` + `yerel-gitops`'ta `apps/<ad>.yaml` ve `<ad>/` |

### Sirlar ve yerel dosyalar (hepsi git disi)

| Dosya | Icerik |
|---|---|
| `.vault/init.json` | Unseal anahtari + kok token. Yalniz bu Windows kullanicisi okur (NTFS ACL; Git Bash'te `chmod` etkisizdir). **Kaybolursa Vault acilamaz**: sokup yeniden kurmak gerekir. |
| `.sirlar/<ad>.env` | Uygulama sirlari, `ANAHTAR=deger` satirlari (tirnaksiz). Ayni ACL. |
| `terraform/*/terraform.tfstate` | Terraform durumu. Sir icermez (T3 dogrular). |
| `yedekler/vault-*.snap` | Vault Raft snapshot'lari (`scripts/vault_yedek.sh`). |

Kabul edilen sinirlar (yalniz yerel ogrenme ortami): 1/1 unseal anahtari ve elle unseal, kok token
yerel dosyada, Kubernetes Secret'lari etcd'de sifresiz, tek dugum, Argo CD'de SSO yok.
````

- [ ] **Step 3: CI'in yerel karsiligi**

```bash
for a in kume yapilandirma; do scripts/tf.sh "$a" fmt -check -recursive && scripts/tf.sh "$a" validate -no-color && scripts/tf.sh "$a" test -no-color | tail -1; done
bash tests/tf_koruma_test.sh | tail -1; bash tests/env_json_test.sh | tail -1; bash tests/izin_test.sh | tail -1
MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W):/r" -w /r alpine:3.20 sh -c \
  "apk add -q bash jq coreutils >/dev/null && bash tests/tf_koruma_test.sh | tail -1 && bash tests/env_json_test.sh | tail -1 && bash tests/izin_test.sh"
MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W)/.github/workflows:/wf" rhysd/actionlint:1.7.7 -no-color /wf/ci.yml && echo actionlint-temiz
MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W):/repo" zricethezav/gitleaks:v8.30.1 git /repo --redact --no-banner --log-opts="main..HEAD"
```

Expected: her asama icin `Success! The configuration is valid.` ve `Success! 1 passed, 0 failed.`; testler `TUM TESTLER GECTI` (Linux'ta izin testi `atlandi: Windows degil`); `actionlint-temiz`; gitleaks `no leaks found`.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml README.md
git commit -m "ci: terraform fmt/validate/test, betik testleri, shellcheck, gitleaks; README B3 bolumu

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Canli kopyaya yerel merge (push yok)

**Files:** yok

**Interfaces:**
- Consumes: `feat/b3a-platform`
- Produces: canli kopya `main`'de B3a kodu; operasyon gorevleri buradan calisir.

- [ ] **Step 1: Merge**

```bash
cd C:/Users/Adanedhel/Desktop/OpenCodeProjects/yerel-platform
git status --short
git merge --no-ff feat/b3a-platform -m "Merge feat/b3a-platform: Terraform + Argo CD + Vault + VSO platformu (B3a)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git log --oneline -1 && ls scripts terraform
docker inspect -f '{{.State.Health.Status}}' yerel-postgres
```

Expected: status bos; merge commit'i; `scripts/` 11 betik (`arayuz.sh k8s_dogrulama.sh ortak.sh repo_anahtari.sh sir_yaz.sh tf.sh uygulama_ekle.sh vault_baslat.sh vault_kilit_ac.sh vault_yedek.sh yedekle.sh`), `terraform/` `kume yapilandirma`; `healthy` (compose'a dokunulmadi).

---

### Task 8 (Operasyon, controller): Platform kurulumu ve Vault baslatma — T1, T2

**Files:** yok (canli kopyada calisir; state ve `.vault/` burada olusur)

**Interfaces:**
- Consumes: Task 2, 4, 5
- Produces: kumede Argo CD, Vault (baslatilmis, acik), VSO; `.vault/init.json`; `terraform/kume/terraform.tfstate`

- [ ] **Step 1: Kullaniciya kisa durum ver** ("Kumeye Argo CD, Vault ve VSO kuruyorum; yalniz docker-desktop.")

- [ ] **Step 2: Plan ve apply**

```bash
cd C:/Users/Adanedhel/Desktop/OpenCodeProjects/yerel-platform
scripts/tf.sh kume init -input=false | tail -1
scripts/tf.sh kume plan -input=false -no-color | grep -E '^Plan:'
scripts/tf.sh kume apply -input=false -auto-approve -no-color | tail -3
for ns in argocd vault vault-secrets-operator; do kubectl --context docker-desktop get pods -n "$ns"; done
```

Expected: `Plan: 6 to add, 0 to change, 0 to destroy.`; `Apply complete! Resources: 6 added, ...`; `vault-0` `0/1 Running` (kilitli), digerleri `Running`.

- [ ] **Step 3: Vault'u baslat**

```bash
scripts/vault_baslat.sh
git status --short --ignored .vault | head -2
```

Expected: `Vault baslatildi; anahtar ve kok token: .../.vault/init.json (yalniz bu kullanici)`, `Vault kilidi acik. ...`; `!! .vault/` (ignored).

- [ ] **Step 4: T1, T2**

```bash
scripts/k8s_dogrulama.sh t1 t2
```

Expected: `GECTI  T1 platform: ...; kume plan: No changes` ve `GECTI  T2 Vault: initialized, sealed=false; ...`. T1 "No changes" degilse: plan ciktisindaki kaynak/alan Task 2'ye geri bildirilir (yeni worktree dalinda duzeltme), sonra Step 4 tekrar.

- [ ] **Step 5: Arayuzleri kullaniciya goster**

Kullaniciya su iki komutu ayri terminalde calistirmasini soyle (port-forward on planda kalir; Ctrl+C kapatir):

```bash
scripts/arayuz.sh argocd
```

```bash
scripts/arayuz.sh vault
```

Argo CD ilk parolasi panodadir; giristen sonra parolayi degistirip `argocd-initial-admin-secret`'i silmesini hatirlat (betik komutu basar).

---

### Task 9 (Operasyon, controller): Vault ve Argo CD yapilandirmasi — T3

**Files:** yok

**Interfaces:**
- Consumes: Task 3, 8
- Produces: `terraform/yapilandirma/terraform.tfstate`; Vault auth/KV/audit/politikalar/roller; projeler; kok Application (repo henuz yok: Task 11'e kadar `ComparisonError` normaldir)

- [ ] **Step 1: Apply**

```bash
cd C:/Users/Adanedhel/Desktop/OpenCodeProjects/yerel-platform
scripts/tf.sh yapilandirma init -input=false | tail -1
scripts/tf.sh yapilandirma plan -input=false -no-color | grep -E '^Plan:'
scripts/tf.sh yapilandirma apply -input=false -auto-approve -no-color | tail -2
kubectl --context docker-desktop get appprojects,applications,vaultauths,vaultstaticsecrets -n argocd
```

Expected: `Plan: 14 to add, 0 to change, 0 to destroy.`; `Apply complete! Resources: 14 added, ...`; AppProject `default`, `kisisel`, `platform`; Application `kok`; VaultAuth `argocd-vso`; VaultStaticSecret `yerel-gitops-repo`.

- [ ] **Step 2: T3**

```bash
scripts/k8s_dogrulama.sh t3
```

Expected: `GECTI  T3 yapilandirma: plan No changes; kume/yapilandirma state'lerinde sir yok; audit N istek`.

- [ ] **Step 3: (Yalniz T3 "No changes" degilse) `computed_fields`**

`plan_degisiksiz` ciktisi `~ resource "kubernetes_manifest" "<ad>"` ve degisen alani gosterir. Degisen alan Argo CD/VSO'nun yazdigi bir alansa (or. `metadata.finalizers`, `spec.syncPolicy`), yalniz o `kubernetes_manifest` kaynagina ekle (yeni worktree dalinda, `terraform/yapilandirma/argocd.tf`):

```hcl
  computed_fields = ["metadata.labels", "metadata.annotations", "<degisen.alan>"]
```

`fmt`/`validate`/`test`, commit, `--no-ff` merge, `scripts/tf.sh yapilandirma apply`, sonra Step 2 tekrar. Sonucu ADR'ye not et (Task 12).

---

### Task 10 (Operasyon, controller): `cybernews_k8s` ve uygulama sirlari — T4

**Files:** yok (`.sirlar/tech-radar.env` canli kopyada, git disi)

**Interfaces:**
- Consumes: `scripts/uygulama_ekle.sh` (mevcut), `scripts/sir_yaz.sh`
- Produces: yerel-postgres'te `cybernews_k8s` veritabani + kullanici; `.sirlar/tech-radar.env` (`SECRET_KEY`, `DB_USER=cybernews_k8s`, `DB_PASSWORD`, `GEMINI_API_KEY=` bos); Vault `kv/tech-radar/uygulama`

- [ ] **Step 1: Veritabani + sir dosyasi + Vault (tek komut; parola hicbir yere basilmaz)**

```bash
cd C:/Users/Adanedhel/Desktop/OpenCodeProjects/yerel-platform
mkdir -p .sirlar && bash -c '. scripts/ortak.sh; yalniz_bana .sirlar' && \
PAROLA="$(openssl rand -hex 24)" && \
UYGULAMA_PAROLASI="$PAROLA" scripts/uygulama_ekle.sh cybernews_k8s && \
printf 'SECRET_KEY=%s\nDB_USER=cybernews_k8s\nDB_PASSWORD=%s\nGEMINI_API_KEY=\n' "$(openssl rand -hex 32)" "$PAROLA" > .sirlar/tech-radar.env && \
unset PAROLA && \
scripts/sir_yaz.sh tech-radar && \
bash -c '. scripts/ortak.sh; yalniz_bende_mi .sirlar/tech-radar.env && echo "acl: yalniz bende"'
```

Expected: `hazir: veritabani 'cybernews_k8s', kullanici 'cybernews_k8s' ...`; `baglam yerel: ...`; `yazildi: kv/tech-radar/uygulama (4 anahtar, surum 1)`; `acl: yalniz bende`.

- [ ] **Step 2: Compose'un veritabanina dokunulmadigini dogrula**

```bash
docker exec yerel-postgres psql -U postgres -tAc "select datname from pg_database where datname like 'cybernews%' order by 1"
docker compose -f C:/Users/Adanedhel/Desktop/OpenCodeProjects/CyberNews/cybersecurity_news/docker-compose.yml ps --format '{{.Name}} {{.Status}}' | head -6
```

Expected: `cybernews` ve `cybernews_k8s`; compose servisleri `Up`.

- [ ] **Step 3: T4**

```bash
scripts/k8s_dogrulama.sh t4
```

Expected: `GECTI  T4 en az yetki: tech-radar rolu kv/tech-radar okur (200), kv/argocd okuyamaz (403); t4-baska girisi reddedildi (400|403)`.

---

### Task 11 (Operasyon, controller, DISARIYA DONUK — kullanici onayi): `yerel-gitops` reposu ve deploy key — T5

**Files:** yeni repo `C:/Users/Adanedhel/Desktop/OpenCodeProjects/yerel-gitops`: `README.md`, `apps/README.md`

**Interfaces:**
- Consumes: `scripts/repo_anahtari.sh`, Task 9'un kok Application'i
- Produces: GitHub `AdanedhelWrites/yerel-gitops` (private, `main`); deploy key `argocd-yerel` (read_only); Vault `kv/argocd/yerel-gitops`; Argo CD `repo-yerel-gitops` Secret'i; kok Application Synced. B3b bu klonu kullanir.

- [ ] **Step 1: Kullanicidan onay al**

Sor: "GitHub'da private `AdanedhelWrites/yerel-gitops` reposunu acip ilk commit'i (yalniz README) push edecegim, sonra bu repoya salt okunur bir deploy key ekleyecegim. Onayliyor musun?" Onay gelmeden devam etme.

- [ ] **Step 2: Yerel repo ve ilk commit**

`C:/Users/Adanedhel/Desktop/OpenCodeProjects/yerel-gitops/README.md`:

````markdown
# yerel-gitops

Yerel Docker Desktop Kubernetes kumesinde (`docker-desktop`) **ne calisacagini** tutan GitOps
reposu. Argo CD bu repoyu salt okunur bir deploy key ile 2 dakikada bir okur ve kumeyi buraya
esitler. Elle yapilan degisiklikler geri alinir (self-heal); dogru kaynak bu repodur.

Platform (Argo CD, Vault, Vault Secrets Operator) `AdanedhelWrites/yerel-platform`'da Terraform
ile kurulur. Tasarim: `AdanedhelWrites/tech-radar` `docs/superpowers/specs/2026-10-03-b3-terraform-argocd-vault-design.md`.

## Yapi

| Yol | Ne |
|---|---|
| `apps/` | Her YAML bir Argo CD `Application`'dir. Kok uygulama (`kok`, Terraform) bu dizini kumeye uygular |
| `<uygulama>/` | Uygulamanin degerleri (`values-*.yaml`) ve ek manifestleri (`manifests/`) |

## Kurallar

- **Sir yok.** Sirlar Vault'tadir (`yerel-platform/scripts/sir_yaz.sh`); buraya yalniz Vault yolunu
  gosteren `VaultStaticSecret` girer. CI gitleaks ile tarar.
- Bu repoya her push kumeyi degistirir: push oncesi CI'in yerel karsiligini calistirin.
````

`C:/Users/Adanedhel/Desktop/OpenCodeProjects/yerel-gitops/apps/README.md`:

````markdown
# apps/

Bu dizindeki her `*.yaml` bir Argo CD `Application`'dir (proje `kisisel`). Kok uygulama `kok`
(yerel-platform Terraform'u, proje `platform`) dizini izler: dosya eklemek uygulamayi kurar,
silmek uygulamayi ve kaynaklarini kaldirir (finalizer). README gibi YAML olmayan dosyalar yok sayilir.
````

```bash
cd C:/Users/Adanedhel/Desktop/OpenCodeProjects/yerel-gitops
git init -b main
printf '* text=auto eol=lf\n' > .gitattributes
git add .gitattributes README.md apps/README.md
git commit -m "docs: yerel-gitops iskeleti (Argo CD kok uygulamasi apps/ dizinini izler)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W):/repo" zricethezav/gitleaks:v8.30.1 git /repo --redact --no-banner
```

Expected: commit; gitleaks `no leaks found`.

- [ ] **Step 3: GitHub reposunu ac ve push et (onayli)**

```bash
cd C:/Users/Adanedhel/Desktop/OpenCodeProjects/yerel-gitops
gh repo create AdanedhelWrites/yerel-gitops --private --source . --remote origin --push \
  --description "Yerel docker-desktop kumesi icin GitOps (Argo CD)"
gh repo view AdanedhelWrites/yerel-gitops --json visibility,defaultBranchRef -q '.visibility + " " + .defaultBranchRef.name'
```

Expected: `PRIVATE main`.

- [ ] **Step 4: Deploy key (onayli)**

```bash
cd C:/Users/Adanedhel/Desktop/OpenCodeProjects/yerel-platform
scripts/repo_anahtari.sh AdanedhelWrites/yerel-gitops
```

Expected: `ozel anahtar Vault'ta: kv/argocd/yerel-gitops`; `deploy key eklendi: AdanedhelWrites/yerel-gitops (argocd-yerel, read_only)`.

- [ ] **Step 5: T5**

```bash
kubectl --context docker-desktop -n argocd annotate vaultstaticsecret yerel-gitops-repo yerel-platform/yenile="$(date +%s)" --overwrite
scripts/k8s_dogrulama.sh t5
```

Expected: `GECTI  T5 repo erisimi: deploy key read_only; Secret VSO'dan; kok Application Synced @ <sha7>`.

---

### Task 12 (Operasyon, controller): T11, B3a kapisi, belgeler ve push (onayli)

**Files:**
- Modify: tech-radar `docs/ADR-0008-Yerel-GitOps-Terraform-ArgoCD-Vault.md` (Consequences altina "Sonuc (B3a)")

**Interfaces:**
- Consumes: Task 8-11
- Produces: B3a kapisi GECTI; push'lar (onayli)

- [ ] **Step 1: T11 ve tam kapi**

```bash
cd C:/Users/Adanedhel/Desktop/OpenCodeProjects/yerel-platform
scripts/k8s_dogrulama.sh t11
scripts/k8s_dogrulama.sh b3a 2>&1 | tee /tmp/b3a-kapi.txt | grep -E '^(GECTI|KALDI)|KAPISI'
scripts/vault_yedek.sh
```

Expected: `GECTI  T11 ...`; ardindan T1, T2, T3, T4, T5, T11 `GECTI` ve `B3a KAPISI GECTI (T1-T5, T11)`; `Vault snapshot: .../yedekler/vault-<zaman>.snap (N bayt)`.

- [ ] **Step 2: Arta kalan port-forward yok**

PowerShell:

```powershell
Get-CimInstance Win32_Process -Filter "Name='kubectl.exe'" | Where-Object { $_.CommandLine -match 'port-forward' } | Select-Object ProcessId, CommandLine
```

Expected: bos (ya da yalniz kullanicinin `arayuz.sh` ile actiklari; onlara dokunma).

- [ ] **Step 3: ADR-0008'e B3a sonucu** (tech-radar canli kopyasinda, `## Consequences` bolumundeki `- **Sonuc:** ...` satirinin altina)

```markdown
- **Sonuc (B3a, <tarih>):** `yerel-platform` `scripts/k8s_dogrulama.sh b3a` GECTI.

  | # | Sonuc |
  |---|---|
  | T1 | <cikti satiri> |
  | T2 | <cikti satiri> |
  | T3 | <cikti satiri> |
  | T4 | <cikti satiri> |
  | T5 | <cikti satiri> |
  | T11 | <cikti satiri> |

  Olcumler: kumeden `host.docker.internal:5432` prob'u basarili (yedek PostgreSQL gerekmedi);
  surumler argo-cd 10.9.6, vault 0.34.1 (Vault 2.0.4), VSO 1.6.0; provider'lar helm 3.3.0,
  kubernetes 3.3.0, vault 5.12.0. Netlestirmeler: init/unseal HTTP API ile; "600" = NTFS ACL;
  `yerel-gitops` + deploy key ve `cybernews_k8s` B3a'da. <Task 9 Step 3 uygulandiysa computed_fields notu>
```

`<...>` yerlerini `/tmp/b3a-kapi.txt`'teki `GECTI` satirlari ve tarihle doldur.

```bash
cd C:/Users/Adanedhel/Desktop/OpenCodeProjects/CyberNews/cybersecurity_news
git add docs/ADR-0008-Yerel-GitOps-Terraform-ArgoCD-Vault.md
git commit -m "docs: ADR-0008 B3a sonucu (T1-T5, T11 gecti)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 4: Push oncesi gitleaks (iki repo)**

```bash
cd C:/Users/Adanedhel/Desktop/OpenCodeProjects/yerel-platform && git fetch -q origin && \
  MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W):/repo" zricethezav/gitleaks:v8.30.1 git /repo --redact --no-banner --log-opts="origin/main..main"
cd C:/Users/Adanedhel/Desktop/OpenCodeProjects/CyberNews/cybersecurity_news && git fetch -q origin && \
  MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W):/repo" zricethezav/gitleaks:v8.30.1 git /repo --redact --no-banner --log-opts="origin/main..main"
```

Expected: ikisinde de `no leaks found`.

- [ ] **Step 5: Kullanicidan push onayi al, sonra push**

Sor: "yerel-platform (B3a) ve tech-radar (ADR-0008 B3a sonucu) `main`'lerini push edeyim mi?" Onaydan sonra:

```bash
git -C C:/Users/Adanedhel/Desktop/OpenCodeProjects/yerel-platform push origin main
git -C C:/Users/Adanedhel/Desktop/OpenCodeProjects/CyberNews/cybersecurity_news push origin main
gh run list -R AdanedhelWrites/yerel-platform --limit 1
```

Expected: push'lar basarili; `CI` calisiyor/`completed success` (kirmiziysa nedeni duzelt, tekrar push onayi).

- [ ] **Step 6: Temizlik ve durum**

```bash
cd C:/Users/Adanedhel/Desktop/OpenCodeProjects/yerel-platform
git worktree remove ../yerel-platform-b3a && git branch -d feat/b3a-platform
git status --short
```

Expected: worktree silindi; status bos (`.vault/`, `.sirlar/`, state'ler ignored). Kullaniciya ozet: kurulu bilesenler, arayuz komutlari, `vault_kilit_ac.sh` hatirlatmasi, siradaki B3b.
