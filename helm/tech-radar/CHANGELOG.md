# tech-radar chart degisiklik kaydi

Surum kurali (SemVer): uyumsuz values/sablon degisikligi **MAJOR**, yeni istege bagli
deger veya bilesen **MINOR**, davranisi degistirmeyen duzeltme **PATCH**. Chart
dizinindeki her degisiklik `Chart.yaml` `version`'ini artirir ve buraya `## [surum]`
basligi ekler; CI (`scripts/chart_surum_kontrol.sh`) bunu zorlar. `appVersion`
uygulama imajinin etiketidir (CalVer `YYYY.M.N`).

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
