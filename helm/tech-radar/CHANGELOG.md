# tech-radar chart degisiklik kaydi

Surum kurali (SemVer): uyumsuz values/sablon degisikligi **MAJOR**, yeni istege bagli
deger veya bilesen **MINOR**, davranisi degistirmeyen duzeltme **PATCH**. Chart
dizinindeki her degisiklik `Chart.yaml` `version`'ini artirir ve buraya `## [surum]`
basligi ekler; CI (`scripts/chart_surum_kontrol.sh`) bunu zorlar. `appVersion`
uygulama imajinin etiketidir (CalVer `YYYY.M.N`).

## [2.1.1] - 2026-10-08 — appVersion 2026.10.2

Yalniz `appVersion` yukseltmesi; sablon ve values degismedi (render farki yalniz imaj etiketi ve `helm.sh/chart`).
Uygulama 2026.10.2: guvenlik basliklari (django-csp ile CSP, Permissions-Policy, CORP/COEP, WhiteNoise
`Access-Control-Allow-Origin: *` kapali, Swagger UI SplitView; PR #55), `source-map-js` 1.2.2 (PR #52).
Imajlar yerelde derlenir: `teknoloji-haberleri-{api,frontend}:2026.10.2`.

## [2.1.0] - 2026-10-04 — appVersion 2026.10.1

GitOps (Argo CD) ve chart disi secret yonetimi (Vault Secrets Operator) icin istege bagli degerler
([ADR-0008](../../docs/ADR-0008-Yerel-GitOps-Terraform-ArgoCD-Vault.md)). Varsayilan degerlerle
render 2.0.1 ile aynidir (yalniz `helm.sh/chart` etiketi ve ondan turetilen checksum'lar degisir).

### Eklenenler
- `migration.mode` (`helm` varsayilan | `argocd`). `argocd`: Argo CD chart'i `helm template` ile isler ve `.Release.Revision` hep 1'dir; Job sabit adli (`<migration.name>`) bir Argo CD Sync hook'u olur (`argocd.argoproj.io/hook: Sync`, `argocd.argoproj.io/hook-delete-policy: BeforeHookCreation`) ve her senkronda yeniden olusturulur. Gecersiz deger render'i durdurur.
- `secrets.existingSecret` (`""`). Doluysa `teknoloji-secret` olusturulmaz, `secrets.*` `required` kontrolleri atlanir, tum `secretKeyRef`'ler (PostgreSQL dahil) bu Secret'i kullanir ve pod'lara `checksum/secret` yazilmaz (yeniden baslatmayi Secret'in sahibi yapar). Secret anahtarlari: `SECRET_KEY`, `DB_USER`, `DB_PASSWORD`, `GEMINI_API_KEY`.
- `ci/argocd-values.yaml` (CI'da Argo CD + VSO render'i).

## [2.0.1] - 2026-10-03 — appVersion 2026.10.1

Duzeltme; render edilen manifestler degismez (yalniz `helm.sh/chart` etiketi ve ondan turetilen checksum'lar).

### Duzeltilenler
- `templates/NOTES.txt` git'e girdi: `.gitignore`'daki `*.txt` kurali dosyayi disliyordu, chart NOTES'suz yayinlaniyordu.
- `NOTES.txt` 2.0.0'da kaldirilan `global.namespace` yerine `.Release.Namespace` kullanir; `kubectl ... -n` ipuclari bos namespace ile cikiyordu.

## [2.0.0] - 2026-10-01 — appVersion 2026.10.1

Ilk gercek kurulum: yerel docker-desktop dogrulamasi
([ADR-0007](../../docs/ADR-0007-PostgreSQL-Gecisi-ve-Helm-Dogrulamasi.md)). Geriye uyumsuz.

### Yukseltme notu (1.0.0 -> 2.0.0)
- `secrets.postgresPassword` kalkti. PostgreSQL ve uygulama tek `secrets.dbPassword`'u kullanir; artik zorunlu.
- `global.namespace` ve `templates/namespace.yaml` kalkti: `-n <namespace> --create-namespace` kullanin.
- `config.django.allowedHosts` kalkti: `ALLOWED_HOSTS` sablonda kurulur; ek host icin `config.django.extraAllowedHosts`.
- `config.database.url` (`DATABASE_URL`) kalkti; uygulama PostgreSQL'i `DB_HOST`'tan secer.
- `backend.image.tag` / `frontend.image.tag` varsayilani `latest` -> `""` (`appVersion`).
- Migration hook'u kalkti; her revizyonda `<migration.name>-r<revizyon>` Job'u calisir.

### Eklenenler
- LibreTranslate Deployment/Service/PVC (`libretranslate.*`). Kok dosya sistemi salt okunur; yazilabilir dizinler: `.local` (PVC, modeller), `.config`, `.cache`, `/app/db` (Prometheus metrik dizini) ve `/tmp` (emptyDir).
- `config.app.*` (`REFRESH_*`, `TRANSLATE_MIN_RATIO`, `RETRANSLATE_*`, `RETENTION_DAYS`, `GEMINI_*`, `LIBRETRANSLATE_*`), `secrets.geminiApiKey`, `config.django.extraCsrfTrustedOrigins`.
- `fsGroup` + `fsGroupChangePolicy`, `migrasyon-bekle` initContainer, configmap/secret checksum annotation'lari, bilesen bazinda `containerSecurityContext`.
- Ucuncu taraf imajlar surum + digest ile sabit (`image.digest`); `ci/yerel-values.yaml`.

### Degisenler
- Backend probe'lari `/api/v1/health/` (`Host: localhost`).
- Statik dosyalar imajda (`collectstatic` build'de); pod'larda `RUN_STARTUP_TASKS=false`.
- PostgreSQL probe'lari `pg_isready -h 127.0.0.1 -d <db>`.

### Duzeltilenler
- Redis `--appendonly yes` argumani tirnaksizdi; YAML'da boolean'a donusuyor ve Kubernetes Deployment'i reddediyordu.

## [1.0.0] - 2026-03-03

Ilk chart. Hic deploy edilmedi (ADR-0007; spec 2.5'teki bulgular).
