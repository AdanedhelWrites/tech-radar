# B3 Devir Notu — yeni oturum icin

- **Tarih:** 2026-10-03
- **Amac:** B3 (Terraform + Argo CD + Vault/VSO ile yerel GitOps) icin iki uygulama planini yazmak,
  sonra Sonnet alt ajanlariyla (subagent-driven-development) uygulamak.
- **Tek yetkili kaynak:** spec [`../specs/2026-10-03-b3-terraform-argocd-vault-design.md`](../specs/2026-10-03-b3-terraform-argocd-vault-design.md)
  ve [ADR-0008](../../ADR-0008-Yerel-GitOps-Terraform-ArgoCD-Vault.md). Bu not spec'in yerine gecmez;
  ortam gercekleri, kurallar ve dersler icindir.

## 1. Yapilacak is

1. `superpowers:writing-plans` ile iki plan yaz (Sonnet'in dogrudan uygulayabilecegi ayrintida: tam
   kod, komutlar, beklenen ciktilar, TDD/dogrulama adimlari, "Spec'e Gore Netlestirmeler"):
   - `docs/superpowers/plans/2026-10-03-b3a-platform.md` — repo `yerel-platform`: `scripts/tf.sh`,
     `terraform/kume`, `scripts/vault_baslat.sh`, `scripts/vault_kilit_ac.sh`, `terraform/yapilandirma`,
     `scripts/sir_yaz.sh`, `scripts/arayuz.sh`, `scripts/k8s_dogrulama.sh` (T1-T5, T11), CI
     (`terraform fmt -check`, `validate`, gitleaks). Kapi: T1-T5, T11.
   - `docs/superpowers/plans/2026-10-03-b3b-gitops.md` — tech-radar chart 2.1.0 (`migration.mode`,
     `secrets.existingSecret`, CHANGELOG, CI etiket kontrolu, `chart-2.1.0` etiketi), yeni repo
     `yerel-gitops` (Application, values-yerel, VSO nesneleri, CI), deploy key, `cybernews_k8s`,
     T6-T10, T12, ADR-0008 sonucu. Kapi: T6-T10, T12. B3a'ya baglidir.
2. Planlar tech-radar reposuna (`docs/superpowers/plans/`) commit edilir (spec ile ayni yer).
3. Kullanici onayindan sonra uygulama: B3a, sonra B3b.

## 2. Plan yazmadan once dogrulanacaklar (tahmin etme, olc)

- **Guncel kararli surumler** (sabitlenecek): Helm chart'lari `argo-cd` (argoproj), `vault`
  (hashicorp), `vault-secrets-operator` (hashicorp); Terraform provider'lari `hashicorp/helm`,
  `hashicorp/kubernetes`, `hashicorp/vault`. `helm search repo --versions` (repo ekleyerek) ya da
  Artifact Hub / registry.terraform.io. Helm 4 provider uyumu (helm provider 3.x API'si: `set` liste
  sozdizimi degisti) kontrol edilmeli.
- **VSO CRD API surumu ve alanlari** (`secrets.hashicorp.com/v1beta1`: `VaultAuth`, `VaultStaticSecret`
  `destination.labels`, `rolloutRestartTargets`, `refreshAfter`) — kurulu chart'in CRD'lerinden.
- **Argo CD multi-source Application** sozdizimi (`sources`, `ref: values`, `$values/...`) ve
  Sync hook annotation'lari (`argocd.argoproj.io/hook: Sync`, `hook-delete-policy: BeforeHookCreation`).
- **Ilk prob (B3a'nin ilk gorevi olmali):** kumedeki bir pod `host.docker.internal:5432` ile
  `yerel-postgres`'e (scram parola) baglanabiliyor mu. Baglanamazsa spec 8'deki yedek
  (chart'in kendi PostgreSQL'i) plana islenir.
- **Docker Desktop bellegi** (`docker info` MemTotal) >= 8 GB mi.
- **Terraform kurulu degil:** `winget install Hashicorp.Terraform` — kullanici kurar ya da onaylar.

## 3. Ortam gercekleri (2026-10-03 itibariyle)

| Konu | Deger |
|---|---|
| Isletim sistemi / kabuk | Windows 11, Git Bash (Bash araci) + PowerShell |
| tech-radar | `C:/Users/Adanedhel/Desktop/OpenCodeProjects/CyberNews/cybersecurity_news`, `main` @ `cb27d9e` (origin'den 1 commit onde: B3 spec + ADR-0008, push edilmedi) |
| yerel-platform | `C:/Users/Adanedhel/Desktop/OpenCodeProjects/yerel-platform`, GitHub `AdanedhelWrites/yerel-platform` **private**, `main` @ `bb5c026` (pushlu) |
| yerel-gitops | Henuz yok (acmak kullanici onayi ister) |
| Kubernetes | Docker Desktop **kubeadm**, tek dugum `docker-desktop`, v1.36.1, runtime `docker://29.7.2` (yerel imajlar kumede gorunur), sunucu `https://kubernetes.docker.internal:6443` |
| **Aktif kubectl baglami** | **`aks-gokbulut` (baska projenin uretim AKS'i) — ASLA kullanilmaz** |
| Docker imaj deposu | `overlay2` (containerd store KAPALI). kind saglayicisi bu yuzden calismadi; acmak canli yiginin imajlarini gizler |
| Helm | 4.3.0, PATH'te degil: `$LOCALAPPDATA/Microsoft/WinGet/Packages/Helm.Helm_Microsoft.Winget.Source_8wekyb3d8bbwe/windows-amd64/helm.exe` (betikler PATH'e ekler) |
| Canli yigin | compose: `teknoloji-api/worker/scheduler/frontend/redis/translate` + `yerel-postgres` (yerel-platform). DB `cybernews`, parola CyberNews `.env` `DB_PASSWORD` |
| Paylasilan PostgreSQL | `yerel-postgres` (16.15 digest), `127.0.0.1:5432`, ag `yerel-platform`, superuser parolasi yerel-platform `.env`; uygulama ekleme `scripts/uygulama_ekle.sh` |
| tech-radar chart | 2.0.0, appVersion `2026.10.1`; `scripts/helm_yerel_dogrulama.sh` (S1-S7) gecti |
| Test yardimcisi | `scripts/pg_test.sh` (tek kullanimlik PostgreSQL + Redis ile `manage.py`); 375 test |

## 4. Kurallar (kullanici kararlari — degismez)

- **Yalniz yerel.** `aks-gokbulut` yasak; her kubectl `--context docker-desktop`, her helm
  `--kube-context docker-desktop`, Terraform yalniz `tf.sh` ile. `use-context` asla.
- **Disariya donuk her adim onayla:** repo acmak, deploy key, etiket push'u, `git push`.
  Push oncesi yerel gitleaks (`zricethezav/gitleaks:v8.30.1`, `--log-opts=origin/main..main`).
- **Sirlar** git'e, Terraform state'ine ve ekrana girmez; gerekirse panoya (`| clip.exe`).
- **Review politikasi:** gorev basina subagent review yok; kapi = testler + controller'in bagimsiz
  dogrulamasi (dosyayi plana bayt bayt karsilastirma, testleri yeniden kosturma). Riskli diff'te tek
  sonnet review. Implementer modeli **sonnet**.
- **Operasyon gorevleri** (gercek kume/canli yigin/sir iceren) controller kosar, alt ajana verilmez.
- **Kullanici dili Turkce**; aciklamalari "cocuga anlatir gibi" mantikla ister; her onemli adimda
  kisa durum. Gunluk notu: `C:/Users/Adanedhel/Documents/Obsidian Vault/Daily/<tarih>.md` (hook ister).
- Kod/yorum/commit ASCII Turkce; commit sonu `Co-Authored-By:` satiri; `--no-ff` merge; worktree'ler
  `../<repo>-<is>` (canli kopyada dal degistirilmez).

## 5. Ogrenilen dersler (planlara yansit)

1. **Git Bash yol cevirisi:** `docker run/compose run ... /app/...` argumanlari `C:/Program Files/Git/...`
   olur -> `MSYS_NO_PATHCONV=1` sart (B1'de bir dump bu yuzden kayboldu).
2. **`compose run ... teknoloji-api manage.py`** icin `--entrypoint python` sart (entrypoint migrate calistirir).
3. **Mutasyon kontrolu:** yeni testin kodu gercekten sinadigini, kodu gecici bozup kirmizi gorerek
   dogrula (B1'de M2M testleri bos cikmisti).
4. **`DEBUG=False` calisan her yer `DB_HOST` ister** (CI, DAST, Helm). Yeni bir calistirma yolu
   eklenirse ayni ortam degiskenleri verilmeli.
5. **readOnlyRootFilesystem:** her yeni imaj yazdigi dizinleri bulmak icin gercek kurulumda denenmeli
   (LibreTranslate `.config` + `/app/db` gerekti). Gevsetmek yerine `emptyDir`.
6. **nginx:** regex `location` bloklari `^~`'siz onek bloklarindan oncelikli.
7. **Argo CD `helm template` kullanir:** `.Release.Revision` hep 1, `lookup` calismaz, Helm hook'lari
   Argo hook'larina cevrilir — chart 2.1.0 `migration.mode=argocd` bu yuzden.
8. **Port-forward'lar** arka planda `kubectl.exe` olarak kalabilir; is bitince
   `Get-CimInstance Win32_Process -Filter "Name='kubectl.exe'"` ile kontrol edip yalniz kendi
   acilanlari kapat (worktree silmeyi kilitlemisti).
9. **Python'u bash heredoc icinde tek tirnakli string'le yazma** (kesme isareti kirar); betigi dosyaya yaz.
10. Docker Desktop kubeadm kumesi ilk acilista kubeconfig'i gec gunceller; API `livez` 200 olsa da
    dugum Ready olana kadar bekle.

## 6. Acik isler

- **B1 48 saatlik olcum** (B1 Task 10): 2026-10-04 02:15'ten sonra; gecis oncesi max FetchRun id **321**;
  sorgu `docs/superpowers/plans/2026-10-01-faz-b1-postgres.md` Task 10'da; sonuc ADR-0007'ye.
- **`cb27d9e` push'u** (B3 spec + ADR-0008) — kullanici onayi.
- Ertelenmis kucuk bulgular: Dockerfile `RUN` satir devami tek satira birlesmis (islev ayni);
  `helm_yerel_dogrulama.sh`'ta iki em-dash; `.gitignore`'da fazla bos satir.

## 7. Yeni oturumu baslatma metni

> CyberNews B3: `docs/superpowers/plans/2026-10-03-b3-devir-notu.md`'yi ve spec'i
> (`docs/superpowers/specs/2026-10-03-b3-terraform-argocd-vault-design.md`) oku. Devir notundaki
> "dogrulanacaklar"i olc, sonra superpowers:writing-plans ile B3a ve B3b planlarini yaz.
> Kurallar devir notunda; aks-gokbulut'a asla dokunma.
