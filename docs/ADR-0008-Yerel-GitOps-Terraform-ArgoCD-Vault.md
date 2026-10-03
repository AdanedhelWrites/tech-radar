# ADR 0008: Yerel GitOps — Terraform, Argo CD ve Vault (B3)

## Status
Accepted (tasarim) — 2026-10-03. Uygulanmadi.

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
