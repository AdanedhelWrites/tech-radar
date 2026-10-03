# ADR 0008: Yerel GitOps — Terraform, Argo CD ve Vault (B3)

## Status
Accepted — 2026-10-03; uygulandi 2026-10-04 (B3a + B3b).

Tasarim: [`superpowers/specs/2026-10-03-b3-terraform-argocd-vault-design.md`](superpowers/specs/2026-10-03-b3-terraform-argocd-vault-design.md). Planlar: `superpowers/plans/2026-10-03-b3a-platform.md`, `superpowers/plans/2026-10-03-b3b-gitops.md`.

## Context
Chart 2.0.0 yerel `docker-desktop` kumesinde `helm install` ile dogrulandi ([ADR-0007](ADR-0007-PostgreSQL-Gecisi-ve-Helm-Dogrulamasi.md)). Kurulum, surum yukseltme ve rollback hala elle komuta bagli. Ekip Terraform, git'ten yonetilen Argo CD ve HashiCorp Vault + Vault Secrets Operator kullaniyor; ayni zincir kisisel ortamda kurulacak. Yerel kume disaridan erisilemedigi icin CI'dan push tabanli dagitim uygun degil.

## Decision
1. **Iki asamali Terraform** (`yerel-platform/terraform`): `kume` Argo CD, Vault (tek dugum, Raft) ve VSO'yu kurar; `yapilandirma` Vault'u (audit, KV v2, Kubernetes auth, uygulama basina en az yetki), AppProject'leri, Argo CD repo erisimini ve kok Application'i olusturur. Baglam `docker-desktop`'a kilitli (`tf.sh` + degisken dogrulamasi).
2. **Genel GitOps reposu** `yerel-gitops` (private): "app of apps"; tech-radar Application'i chart'i `tech-radar` reposunun `chart-<surum>` etiketinden, degerleri ve VSO nesnelerini `yerel-gitops`'tan alir.
3. **Sirlar Vault'ta, Kubernetes'e VSO tasir**; sir degerleri git'e ve Terraform state'ine girmez.
4. **K8s tech-radar paralel deneme ortami** (`cybernews_k8s`, Gemini ve Beat kapali); compose canli kalir.
5. **Chart 2.1.0:** `migration.mode=argocd` (Argo CD `helm template` kullandigi icin `.Release.Revision` hep 1; Job Sync hook olur) ve `secrets.existingSecret`.

### Elenen alternatifler
Bkz. spec bolum 2 ve 11 (CI'dan `helm upgrade`, Terraform ile uygulama dagitimi, Flux, Sealed Secrets, ESO, Agent Injector, commit SHA, OCI registry, uygulamaya ozel CD reposu, Vault dev modu).

## Consequences
- **Positive:** Kumede ne calistigi git'te surumlu; rollback `git revert`; sapma kendiliginden duzelir; sir rotasyonu pod'lari kendiliginden yeniler; yeni kisisel uygulama bir klasor + bir liste elemani. Ekip pratigiyle ayni zincir.
- **Negative / kabul edilen sinirlar:** Vault 1/1 anahtar ve elle unseal, kok token yerel dosyada, etcd'de Secret'lar sifresiz, tek dugum, SSO yok, polling (webhook yok). Spec bolum 10.
- **Sonuc:** (B3a/B3b uygulamasinda T1-T12 sonuclariyla doldurulacak.)
- **Sonuc (B3a, 2026-10-04):** `yerel-platform` `scripts/k8s_dogrulama.sh b3a` GECTI (yerel-platform `main` @ `af5aa91`).

  | # | Sonuc |
  |---|---|
  | T1 | argocd, vault, vault-secrets-operator pod'lari Ready; `tf.sh kume plan`: No changes |
  | T2 | Vault initialized, sealed=false; `.vault/init.json` yalniz bu kullanicida (NTFS ACL) ve git disi |
  | T3 | `tf.sh yapilandirma plan`: No changes; kume/yapilandirma state'lerinde sir yok; audit kaydi dolu |
  | T4 | `tech-radar` rolu `kv/tech-radar` okur (200), `kv/argocd` okuyamaz (403); `t4-baska` namespace'inden giris reddedildi (403) |
  | T5 | `yerel-gitops` (private) deploy key `argocd-yerel` read_only; repo Secret'i VSO'dan; kok Application Synced @ `6701e9a` |
  | T11 | `vault-0` silindi -> kilitliyken repo Secret'i ve kok Application yerinde, VSO okuma hatasi; kilit acilinca VSO yeniden okudu |

  Olcumler: kumeden `host.docker.internal:5432` prob'u basarili (yedek PostgreSQL gerekmedi);
  surumler argo-cd 10.9.6, vault 0.34.1 (Vault 2.0.4), VSO 1.6.0; provider'lar helm 3.3.0,
  kubernetes 3.3.0, vault 5.12.0. Netlestirmeler: init/unseal HTTP API ile; "600" = NTFS ACL;
  `yerel-gitops` + deploy key ve `cybernews_k8s` B3a'da. Asama 2'de `computed_fields` gerekmedi.
  Operasyonda bulunan hata: `env_json` "bicimsiz satir" kontrolu `grep -v` eslesme bulamayinca
  `set -e` + `pipefail` altinda cagirani sessizce dusuruyordu (`sir_yaz.sh`); birim testi `-e`'siz
  kostugu icin kacirmisti. Duzeltme `af5aa91` (`{ grep ... || true; }` + `set -e` altinda test);
  B3a plan dokumanindaki eski satir duzeltilmedi, repo esastir.
- **Sonuc (B3b, 2026-10-04):** chart 2.1.0 (`chart-2.1.0`, tech-radar `3b508e0`), `yerel-gitops`
  tech-radar Application'i (`1aca3e0`); T6-T12 GECTI (yerel-platform `main` @ `bfbf723`).

  | # | Sonuc |
  |---|---|
  | T6 | Application Synced+Healthy; `teknoloji-secret` VSO'dan; migration hook Complete; uygulama `cybernews_k8s`'te; health 200, schema 401, frontend/admin/static 200; SRE cekimi `success`; scheduler 0 replika |
  | T7 | `yerel-gitops` `2315cb9` (`retentionDays: "91"`) senkronlandi; worker `RETENTION_DAYS=91`; migration hook ikinci kez olustu ve Complete |
  | T8 | `git revert` (`e046038`) senkronlandi; `RETENTION_DAYS=90` |
  | T9 | Elle `scale 3` -> self-heal ile 60 sn icinde 1 |
  | T10 | `cybernews_k8s` parolasi degisti -> Vault -> Secret guncellendi (VSS annotation ile aninda) -> pod'lar yeniden basladi; health 200, DB sorgusu calisiyor |
  | T11 | `vault-0` silindi -> kilitliyken Secret, kok Application ve tech-radar (health 200) ayakta; kilit acilinca VSO yeniden okudu |
  | T12 | Sokum (Application'lar, namespace'ler, Vault PV'si, Argo CD CRD'leri) + ayni komutlarla yeniden kurulum (yeni Vault anahtarlari, deploy key yenilendi); T1-T6 ve T11 yeniden GECTI |

  Bulgular: (1) `.env` api imajina giriyordu: `.dockerignore` duzeltildi; compose `:latest` imaji
  `.env`'siz yeniden derlendi ve eski imaj silindi. (2) T11'in onkosulu eksikti: sifirdan kurulumdan
  hemen sonra uygulama pod'lari Ready olmadan Vault yeniden baslatiliyordu (health 000); T11 artik
  once Application'in Healthy olmasini bekler (`bfbf723`). (3) Plan hatasi: `yerel-gitops`
  yamllint'i is akisi dosyasini da tariyordu; `.github/` yamllint disina alindi (actionlint denetler).
  (4) VSO aninda yenileme belgelenmis bir annotation degil, VSS annotation degisikliginin reconcile
  tetiklemesi (`yerel-platform/yenile`). Compose canli ortami (`cybernews`) hicbir adimda etkilenmedi.
