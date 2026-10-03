# B3 — Terraform + Argo CD + Vault ile Yerel GitOps — Tasarim

- **Tarih:** 2026-10-03
- **Durum:** Tasarim onaylandi (bolum 1-5 kullanici onayindan gecti). Uygulanmadi.
- **Planlar:** `../plans/2026-10-03-b3a-platform.md` (B3a), `../plans/2026-10-03-b3b-gitops.md` (B3b)
- **Kapsam:** Yerel Docker Desktop Kubernetes kumesine (`docker-desktop`) Terraform ile Argo CD,
  HashiCorp Vault ve Vault Secrets Operator (VSO) kurmak; ayri bir GitOps reposundan tech-radar'i
  surumlu olarak Argo CD ile dagitmak; surum yukseltme, rollback, sapma ve sir rotasyonunu
  gercek kurulumla dogrulamak.
- **Iliskili:** [ADR-0008](../../ADR-0008-Yerel-GitOps-Terraform-ArgoCD-Vault.md),
  [ADR-0007](../../ADR-0007-PostgreSQL-Gecisi-ve-Helm-Dogrulamasi.md) (chart 2.0.0, yerel-platform PostgreSQL),
  `2026-10-01-faz-b-postgres-helm-design.md` bolum 14 (B3 kapsam notu).
- **Repolar:** `AdanedhelWrites/tech-radar` (public, mevcut), `AdanedhelWrites/yerel-platform`
  (private, mevcut), `AdanedhelWrites/yerel-gitops` (private, yeni).

## 1. Neden

- Ekip Terraform ve git'ten yonetilen Argo CD kullaniyor; secret yonetimi HashiCorp Vault +
  Vault Secrets Operator. Kullanici bu zinciri kendi kisisel ortaminda ogrenmek ve tech-radar'i
  bu yolla dagitmak istiyor.
- B2 chart'i (2.0.0) `helm install` ile dogruladi; surum yukseltme ve rollback henuz git'e
  dayali degil, kurulumlar kisinin komutuna bagli.
- Yerel kume disaridan erisilemez: GitHub Actions'tan push tabanli dagitim (CI'in kumeye
  baglanmasi) mumkun ve guvenli degil. Cekme modeli (kume git'i kendisi okur) dogal secim.

## 2. Kararlar

| # | Karar | Gerekce / elenen |
|---|---|---|
| K1 | **Genel GitOps reposu** `yerel-gitops` (private): tum kisisel uygulamalarin "kumede ne calissin" listesi | Uygulamaya ozel CD reposu (her uygulama icin yeni repo) ve yerel-platform icinde klasor (altyapi ile uygulama surumleri karisir) elendi |
| K2 | **Chart surumu git etiketiyle**: tech-radar reposunda `chart-<surum>` (or. `chart-2.1.0`); Argo CD chart'i o etiketten okur | Commit SHA (okunmaz) ve yerel OCI registry (ek bilesen) elendi. "Git tag yok" kurali chart etiketleri icin bilincli esnetildi; etiket bir yayin/kurulum degil, isarettir |
| K3 | **Sirlar HashiCorp Vault'ta; Kubernetes'e Vault Secrets Operator (VSO) tasir** | Ekip VSO kullaniyor; HashiCorp'un resmi operatoru; Vault Kubernetes auth'unu ve kisa omurlu token'lari dogrudan kullanir; sir degisince `rolloutRestartTargets` ile pod'lari yeniden baslatir. Sealed Secrets (ekipten uzak), ESO (saglayici bagimsizligi burada gereksiz), Agent Injector/CSI (uygulama dosyadan okumali; daha buyuk degisiklik) elendi. Ilk tercih ESO idi, kullanici ekibin VSO kullandigini belirtince degisti |
| K4 | **K8s tech-radar = paralel deneme ortami**: compose canli kalir; K8s ayri `cybernews_k8s` veritabanini kullanir, Gemini kapali, zamanlanmis cekim kapali | "K8s yeni canli" (Docker Desktop kapaninca servis kapanir, ek gecis) ve "kisa omurlu test" (GitOps dongusu yasanmaz) elendi |
| K5 | **Yaklasim A: iki asamali Terraform + "app of apps"**: altyapi Terraform'da, uygulamalar git'te | B: her seyi Terraform (uygulama surumleri altyapi koduna girer, sirlar state'e duser); C: Argo CD her seyi yonetsin (Vault init ve repo erisimi tavuk-yumurta) elendi |
| K6 | **Argo CD neden:** cekme modeli + ekip araci + web arayuzu (sync, saglik, fark, gecmis) | Flux uygun ama arayuzsuz ve ekipte yok; CI'dan `helm upgrade` kumeye erisemez; Terraform `helm_release` ile uygulama GitOps'u bozar |

## 3. Guvenlik siniri

1. **`aks-gokbulut`'a hicbir kosulda dokunulmaz.** Terraform yalniz `scripts/tf.sh` sarmalayicisiyla
   calisir: baglam `docker-desktop`, sunucu yerel (`127.0.0.1`, `localhost`, `kubernetes.docker.internal`),
   dugum `docker-desktop`/`desktop-*` degilse hicbir sey calistirmaz. Provider'larda
   `config_context` bir degiskenden gelir ve degisken `validation` ile yalniz `docker-desktop`'i kabul eder.
   `kubectl config use-context` hic cagrilmaz. Test betigi de ayni korumayi tasir.
2. **Hicbir ortama release yok:** registry yok, uzak kume yok. Disariya donuk adimlar (yerel-gitops
   reposunu acmak, deploy key eklemek, `chart-*` etiketini push etmek, push'lar) kullanici onayiyla.
3. **Gercek kume talimatlari** yalniz `<placeholder>` sablonu olarak yazilir.

## 4. Repolar ve dizinler

### 4.1 `tech-radar` (public)
- Chart `helm/tech-radar`; her chart surumu icin degismez git etiketi `chart-<Chart.yaml version>`.
- Chart **2.1.0** (MINOR; yeni istege bagli degerler, bolum 6.1).
- Imajlar yerelde `appVersion` etiketiyle derlenir (`teknoloji-haberleri-api:2026.10.1`); Docker
  Desktop kubeadm kumesi yerel imajlari gorur.

### 4.2 `yerel-platform` (private)
```
yerel-platform/
├── docker-compose.yml, scripts/uygulama_ekle.sh, scripts/yedekle.sh   (mevcut: PostgreSQL)
├── terraform/
│   ├── kume/            # asama 1: Argo CD, Vault, VSO (helm provider; chart surumleri sabit)
│   └── yapilandirma/    # asama 2: Vault ayarlari, AppProject'ler, repo erisimi, kok Application
├── scripts/
│   ├── tf.sh            # baglam korumali Terraform sarmalayicisi
│   ├── vault_baslat.sh  # bir kez: init + unseal; anahtarlar .vault/init.json (600, git disi)
│   ├── vault_kilit_ac.sh# Docker Desktop yeniden baslayinca unseal
│   ├── sir_yaz.sh       # uygulama sirlarini yerel dosyadan Vault'a yazar (ekrana basmadan)
│   ├── arayuz.sh        # argocd|vault icin port-forward + (argocd) ilk parolayi panoya
│   └── k8s_dogrulama.sh # T1-T12 (baglam kilitli)
└── .gitignore           # + .vault/, terraform/**/.terraform/, *.tfstate*, sir dosyalari
```
- Terraform state yerel dosya, git disi. `.terraform.lock.hcl` git'e girer (provider surumleri sabit).

### 4.3 `yerel-gitops` (private, yeni)
```
yerel-gitops/
├── apps/
│   └── tech-radar.yaml        # Argo CD Application (uc kaynak)
└── tech-radar/
    ├── values-yerel.yaml      # deneme ortami degerleri (sir yok)
    └── manifests/
        ├── serviceaccount.yaml      # tech-radar-vso
        ├── vaultauth.yaml           # Vault kubernetes auth, rol tech-radar
        └── vaultstaticsecret.yaml   # kv/tech-radar/uygulama -> teknoloji-secret
```

### 4.4 Kumedeki namespace'ler
`argocd`, `vault`, `vault-secrets-operator`, `tech-radar` (Argo CD olusturur).

## 5. Terraform asamalari ve Vault'un baslatilmasi

### 5.1 Asama 1 — `terraform/kume` (helm + kubernetes provider)
| Bilesen | Ayar |
|---|---|
| Argo CD (`argocd`) | Resmi `argo-cd` chart'i, surum sabit. Servisler ClusterIP; arayuz yalniz port-forward. Ilk admin parolasi `argocd-initial-admin-secret`'tan `arayuz.sh` ile panoya; ilk giristen sonra parola degistirilir ve bu Secret silinir |
| Vault (`vault`) | Resmi `vault` chart'i, surum sabit. Tek dugum, **Raft depolama (PVC)**, dev modu degil. UI acik (yalniz port-forward). Agent injector kapali |
| VSO (`vault-secrets-operator`) | Resmi chart, surum sabit. Varsayilan `VaultConnection`: `http://vault.vault.svc:8200` |

Chart surumleri plan yazilirken guncel kararli surumlerden secilip sabitlenir.

### 5.2 `scripts/vault_baslat.sh` (bir kez)
- `kubectl exec vault-0 -- vault operator init -key-shares=1 -key-threshold=1 -format=json`
  -> `yerel-platform/.vault/init.json` (izin 600, git disi, ekrana basilmaz).
- `vault operator unseal`. Kilitliyse `vault_kilit_ac.sh` ayni anahtarla acar.
- Vault kilitliyken uygulamalar calismaya devam eder (VSO'nun yazdigi Kubernetes Secret'lari durur);
  yalniz sir yenilemesi bekler.

### 5.3 Asama 2 — `terraform/yapilandirma` (vault + kubernetes provider)
Vault token'i yalniz ortam degiskeninden (`VAULT_TOKEN`, `.vault/init.json`'dan `tf.sh` okur);
Vault adresi `tf.sh`'in actigi port-forward (`http://127.0.0.1:8200`). **Hicbir sir degeri
Terraform'a verilmez.**
- **Audit device** (stdout; `kubectl logs vault-0`).
- **KV v2** `kv/`.
- **Kubernetes auth** (`auth/kubernetes`; Vault kume icinde, kendi SA token'iyla dogrular).
- **Uygulama listesi** `uygulamalar = ["tech-radar"]` (`for_each`): her uygulama icin politika
  (`kv/data/<ad>/*` okuma) ve rol (yalniz `<ad>` namespace'indeki `<ad>-vso` ServiceAccount'u).
- **Argo CD repo erisimi:** politika `argocd-repo` (`kv/data/argocd/*` okuma), rol (yalniz
  `argocd` namespace'indeki VSO SA'si); `argocd` namespace'inde `VaultAuth` +
  `VaultStaticSecret` -> `argocd.argoproj.io/secret-type: repository` etiketli Secret.
- **AppProject'ler:**
  - `platform`: kaynak yalniz `yerel-gitops` (`apps/`), hedef yalniz `argocd` namespace'i (yalniz Application nesneleri).
  - `kisisel`: kaynak yalniz `tech-radar` ve `yerel-gitops` repolari; hedef uygulama namespace'leri;
    kume genelinde yalniz `Namespace`.
- **Kok Application** (`platform` projesi): `yerel-gitops` `apps/` dizini; `automated: {prune, selfHeal}`.

### 5.4 Sirlar ve deploy key
- `scripts/sir_yaz.sh tech-radar`: git disi yerel dosyadan `kv/tech-radar/uygulama`'ya
  `SECRET_KEY`, `DB_USER` (`cybernews_k8s`), `DB_PASSWORD`, `GEMINI_API_KEY` (bos) yazar.
- `yerel-gitops` icin **salt okunur deploy key** (ed25519): ozel yarisi `kv/argocd/yerel-gitops`'a,
  acik yarisi `gh repo deploy-key add --read-only` ile GitHub'a (kullanici onayi). Gecici anahtar
  dosyasi yazildiktan hemen sonra silinir.
- Veritabani: `yerel-platform/scripts/uygulama_ekle.sh cybernews_k8s`.

### 5.5 Kurulum sirasi
`tf.sh kume apply` -> `vault_baslat.sh` -> `tf.sh yapilandirma apply` -> `uygulama_ekle.sh cybernews_k8s`
+ `sir_yaz.sh tech-radar` + deploy key -> (B3b) `yerel-gitops`'a `apps/tech-radar.yaml` ->
Argo CD kurar.

## 6. GitOps ve tech-radar deneme ortami

### 6.1 Chart 2.1.0 (MINOR)
1. **`migration.mode`** (`helm` varsayilan | `argocd`). Argo CD chart'i `helm template` ile isler;
   `.Release.Revision` hep 1'dir. Bugunku Job adi (`teknoloji-migrate-r{{ .Release.Revision }}`)
   Argo'da sabit kalir ve ikinci senkronda Job spec'i degistirilemedigi icin "field is immutable"
   ile takilir. `argocd` modunda Job sabit adlidir ve `argocd.argoproj.io/hook: Sync`,
   `argocd.argoproj.io/hook-delete-policy: BeforeHookCreation` annotation'larini tasir; Argo her
   senkronda yeniden olusturur. Uygulama pod'larinin `migrate --check` initContainer'i degismez.
2. **`secrets.existingSecret`** (`""` varsayilan). Doluysa `secret.yaml` render edilmez, `required`
   kontrolleri atlanir, tum `secretKeyRef`'ler bu Secret'i kullanir; pod'larin `checksum/secret`
   annotation'i render edilmez (yeniden baslatmayi VSO yapar). Secret su anahtarlari icermelidir:
   `SECRET_KEY`, `DB_USER`, `DB_PASSWORD`, `GEMINI_API_KEY`.
3. CHANGELOG `## [2.1.0]`; etiket `chart-2.1.0`.

### 6.2 `apps/tech-radar.yaml`
Proje `kisisel`; uc kaynak:
1. `https://github.com/AdanedhelWrites/tech-radar.git`, `path: helm/tech-radar`,
   `targetRevision: chart-2.1.0`, `helm.releaseName: tech-radar`,
   `helm.valueFiles: [$values/tech-radar/values-yerel.yaml]`.
2. `git@github.com:AdanedhelWrites/yerel-gitops.git`, `targetRevision: main`, `ref: values`.
3. Ayni repo, `path: tech-radar/manifests`.

Hedef namespace `tech-radar`; `syncPolicy.automated: {prune: true, selfHeal: true}`,
`syncOptions: [CreateNamespace=true]`.

### 6.3 `values-yerel.yaml` (sir yok)
`secrets.existingSecret: teknoloji-secret`; `migration.mode: argocd`; `postgresql.enabled: false`;
`config.database.host: host.docker.internal`, `name: cybernews_k8s`; `scheduler.replicas: 0`;
backend/frontend 1 replika; `image.tag` = chart appVersion, `pullPolicy: Never`; ingress kapali;
LibreTranslate acik, kucuk kaynak; `config.django.extraCsrfTrustedOrigins: http://localhost:13000`.

### 6.4 VSO nesneleri (`tech-radar/manifests/`)
- `ServiceAccount tech-radar-vso` (uygulamanin kendi kimliginden ayri: uygulama pod'u Vault'a erisemez).
- `VaultAuth` (method `kubernetes`, mount `kubernetes`, rol `tech-radar`, SA `tech-radar-vso`).
- `VaultStaticSecret` (type `kv-v2`, mount `kv`, path `tech-radar/uygulama`,
  `destination: {name: teknoloji-secret, create: true}`, `refreshAfter: 1h`,
  `rolloutRestartTargets`: `teknoloji-api`, `teknoloji-worker`, `teknoloji-scheduler` Deployment'lari).

## 7. Gunluk akislar

| Akis | Adimlar |
|---|---|
| Yeni uygulama surumu | Kod + CI yesil -> imajlar `<yeni appVersion>` ile yerelde derlenir -> `Chart.yaml` appVersion + version (PATCH) + CHANGELOG -> merge/push -> `chart-<surum>` etiketi push -> `yerel-gitops` `targetRevision` -> Argo CD (<= 3 dk ya da Refresh) migration hook + rolling update |
| Yalniz ayar | `values-yerel.yaml` commit; chart surumu degismez |
| Rollback | `yerel-gitops`'ta `git revert`; Argo CD onceki hale doner. Arayuzdeki Rollback auto-sync'te kapalidir: tek dogru kaynak git. Migration geri alinmaz (expand/contract kurali) |
| Sapma | Elle degisiklik self-heal ile geri alinir; acil mudahalede once auto-sync durdurulur, sonra degisiklik git'e yazilir |
| Sir rotasyonu | `uygulama_ekle.sh` (DB parolasi) + `sir_yaz.sh` (Vault) -> VSO Secret'i gunceller ve pod'lari yeniden baslatir; aninda icin VSO yenileme annotation'i |
| Yeni kisisel uygulama | `uygulama_ekle.sh <ad>` + `uygulamalar` listesine ekle (`tf.sh yapilandirma apply`) + `sir_yaz.sh <ad>` + `yerel-gitops/apps/<ad>.yaml` + `<ad>/` |
| Platform yukseltme | `terraform/kume` chart surumu -> `tf.sh kume plan` -> `apply`; Vault oncesi Raft snapshot |
| Docker Desktop yeniden baslayinca | `vault_kilit_ac.sh` |

Surumun yerleri: uygulama = `appVersion` + imaj etiketi; chart = `Chart.yaml version` + `chart-*`
etiketi; kumede calisan = `yerel-gitops` `targetRevision` (gecmis = git log); platform =
`terraform/kume` sabit surumleri + `.terraform.lock.hcl`.

## 8. Testler (`yerel-platform/scripts/k8s_dogrulama.sh`)

**On kosullar:** Terraform (`winget install Hashicorp.Terraform`, kullanici kurar ya da onaylar);
Docker Desktop bellegi >= 8 GB; **probe:** kumedeki bir pod `host.docker.internal:5432` uzerinden
`yerel-postgres`'e baglanabiliyor mu. Baglanamiyorsa yedek: chart'in kendi PostgreSQL'i
(`postgresql.enabled: true`), veri kumede kalir; karar plana ve ADR-0008'e yazilir.

| # | Senaryo | Kanit |
|---|---|---|
| T1 | Platform kurulumu | Argo CD, Vault, VSO pod'lari Ready; ikinci `tf.sh kume plan` "No changes" |
| T2 | Vault baslatma | `sealed=false`; `.vault/init.json` izin 600 ve `git check-ignore` |
| T3 | Vault yapilandirmasi | ikinci `plan` "No changes"; `terraform state pull` icinde sir degerleri yok; audit kaydi dolu |
| T4 | En az yetki | `tech-radar` rolu `kv/tech-radar` okur, `kv/argocd` okuyamaz; baska namespace'ten giris reddedilir |
| T5 | Repo erisimi | Argo CD `yerel-gitops`'a baglanir; deploy key `read_only: true` |
| T6 | Uygulama | Application Synced + Healthy; `teknoloji-secret` VSO yonetiminde; health 200, schema 401, frontend/admin/static 200; SRE cekimi `cybernews_k8s`'e `success`; scheduler 0 replika |
| T7 | GitOps yukseltme | `yerel-gitops` commit'i -> yeni hal; **migration hook ikinci kez hatasiz** |
| T8 | Rollback | `git revert` -> onceki deger |
| T9 | Sapma | elle `scale 3` -> 60 sn icinde 1 |
| T10 | Sir rotasyonu | Vault degeri degisir -> Secret guncellenir -> pod'lar yeniden baslar -> health 200 |
| T11 | Vault yeniden baslatma | `vault-0` silinir -> kilitli; uygulama health 200; `vault_kilit_ac.sh` -> yenileme surer |
| T12 | Sifirdan kurulum | her sey sokulur ve ayni betik/komutlarla yeniden kurulur; T1 ve T6 tekrar gecer |

Her senaryo GECTI/KALDI basar, ilk hatada durur; cikti plana gore ADR-0008'e islenir.

## 9. CI (GitHub; yerel kumeye erismez)
- **tech-radar:** chart 2.1.0 `migration.mode=argocd` + `existingSecret` render'i ve kubeconform;
  yeni etiket kontrolu (`chart-*` etiketi push edilince surum `Chart.yaml` ile ayni olmali).
- **yerel-gitops:** YAML lint; Application ve VSO CRD semalariyla kubeconform; gitleaks.
- **yerel-platform:** `terraform fmt -check`, `terraform validate`; gitleaks.

## 10. Kabul edilen sinirlar
- Vault 1/1 anahtar ve elle unseal; gercek ortamda 5/3 + bulut KMS auto-unseal.
- Kok token yerel dosyada (git disi, 600); gercek ortamda kullanildiktan sonra iptal edilir.
- Kubernetes Secret'lari etcd'de sifresiz (Docker Desktop).
- Tek dugum, yuksek erisilebilirlik yok; Argo CD'de SSO yok.
- Compose ve K8s ayni sunucuda farkli veritabanlari kullanir; ayni veritabanina ayni anda baglanmazlar.
- Argo CD polling ile calisir (webhook yok; yerel kume disaridan erisilemez).

## 11. Elenen alternatifler
| Alternatif | Neden elendi |
|---|---|
| GitHub Actions'tan `helm upgrade` | Kume disaridan erisilemez; CI'a kume kimligi vermek riskli |
| Terraform `helm_release` ile tech-radar | Uygulama surumleri altyapi koduna girer; sirlar state'e duser |
| Flux | Arayuz yok, ekipte yok |
| Sealed Secrets / ESO / Agent Injector | K3 |
| Commit SHA / OCI registry | K2 |
| Uygulamaya ozel CD reposu | K1 |
| Vault dev modu | Yeniden baslayinca tum sirlar kaybolur |

## 12. Sira ve planlar
| Plan | Repo | Icerik | Kapi |
|---|---|---|---|
| **B3a — platform** | `yerel-platform` | `tf.sh`, `terraform/kume`, `vault_baslat.sh`, `vault_kilit_ac.sh`, `terraform/yapilandirma`, `sir_yaz.sh`, `arayuz.sh`, `k8s_dogrulama.sh` (T1-T5, T11), CI | T1-T5, T11 yesil |
| **B3b — GitOps** | `tech-radar` + `yerel-gitops` | chart 2.1.0 + etiket kontrolu + `chart-2.1.0`; `yerel-gitops` reposu + deploy key; `cybernews_k8s`; T6-T10, T12; ADR-0008 sonucu | T6-T10, T12 yesil |

B3b, B3a'ya baglidir. Disariya donuk adimlarda (repo acma, deploy key, etiket ve push) kullanici onayi.

## 13. Kapsam disi
- Gercek bir kumeye kurulum, registry, SSO, cok dugum.
- K8s'in canli olmasi ve canli verinin K8s'e tasinmasi.
- Vault dinamik sirlari (or. PostgreSQL dinamik kimlik bilgisi) — sonraki adim adayi.
- Argo CD Image Updater (imaj surumunu otomatik yukseltme), bildirimler.
- `pentesterproject` gibi diger uygulamalarin yerel-platform'a tasinmasi.
