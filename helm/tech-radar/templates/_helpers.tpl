{{/*
Chart adi.
*/}}
{{- define "tech-radar.name" -}}
{{- default .Chart.Name .Values.global.appName | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Tam ad.
*/}}
{{- define "tech-radar.fullname" -}}
{{- .Values.global.appName | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Ortak etiketler.
*/}}
{{- define "tech-radar.labels" -}}
app.kubernetes.io/part-of: {{ .Values.global.labels.partOf }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
{{- end }}

{{/*
Bilesen secici etiketi.
*/}}
{{- define "tech-radar.selectorLabels" -}}
app.kubernetes.io/name: {{ .name }}
{{- end }}

{{/*
Imaj referansi (spec K7): etiket bossa .Chart.AppVersion; digest doluysa repo:tag@digest.
Cagiran: include "tech-radar.image" (dict "image" .Values.backend.image "root" $)
*/}}
{{- define "tech-radar.image" -}}
{{- $etiket := toString (.image.tag | default .root.Chart.AppVersion) -}}
{{- if not $etiket -}}
{{- fail (printf "%s icin imaj etiketi yok (image.tag ve Chart.appVersion bos)" .image.repository) -}}
{{- end -}}
{{- if .image.digest -}}
{{ .image.repository }}:{{ $etiket }}@{{ .image.digest }}
{{- else -}}
{{ .image.repository }}:{{ $etiket }}
{{- end -}}
{{- end }}

{{/*
Pod guvenlik baglami — non-root. fsGroup PVC/emptyDir'i ayni gruba yazilabilir kilar.
Cagiran: include "tech-radar.podSecurityContext" .Values.<bilesen>.securityContext
*/}}
{{- define "tech-radar.podSecurityContext" -}}
runAsNonRoot: true
runAsUser: {{ .runAsUser }}
runAsGroup: {{ .runAsGroup }}
fsGroup: {{ .runAsGroup }}
fsGroupChangePolicy: OnRootMismatch
seccompProfile:
  type: RuntimeDefault
{{- end }}

{{/*
Container guvenlik baglami: global.containerSecurityContext + bilesenin kendi
containerSecurityContext'i (bilesen anahtari ezer).
Cagiran: include "tech-radar.containerSecurityContext" (dict "root" $ "bilesen" .Values.backend)
*/}}
{{- define "tech-radar.containerSecurityContext" -}}
{{- $ortak := deepCopy .root.Values.global.containerSecurityContext -}}
{{- $ozel := .bilesen.containerSecurityContext | default dict -}}
{{- toYaml (mergeOverwrite $ortak $ozel) -}}
{{- end }}

{{/*
ALLOWED_HOSTS: localhost (probe'lar Host: localhost gonderir), backend.name
(kume ici tuketici), ingress acikken ingress.host, ve extraAllowedHosts.
*/}}
{{- define "tech-radar.allowedHosts" -}}
{{- $hostlar := list "localhost" .Values.backend.name -}}
{{- if .Values.ingress.enabled -}}
{{- $hostlar = append $hostlar .Values.ingress.host -}}
{{- end -}}
{{- range splitList "," .Values.config.django.extraAllowedHosts -}}
{{- if trim . -}}
{{- $hostlar = append $hostlar (trim .) -}}
{{- end -}}
{{- end -}}
{{- join "," (uniq $hostlar) -}}
{{- end }}

{{/*
CSRF_TRUSTED_ORIGINS: ingress acikken http(s)://<ingress.host>, ve extraCsrfTrustedOrigins.
*/}}
{{- define "tech-radar.csrfTrustedOrigins" -}}
{{- $kaynaklar := list -}}
{{- if .Values.ingress.enabled -}}
{{- $sema := ternary "https" "http" .Values.ingress.tls.enabled -}}
{{- $kaynaklar = append $kaynaklar (printf "%s://%s" $sema .Values.ingress.host) -}}
{{- end -}}
{{- range splitList "," .Values.config.django.extraCsrfTrustedOrigins -}}
{{- if trim . -}}
{{- $kaynaklar = append $kaynaklar (trim .) -}}
{{- end -}}
{{- end -}}
{{- join "," (uniq $kaynaklar) -}}
{{- end }}

{{/*
LIBRETRANSLATE_URL: yalniz libretranslate.enabled iken dolu.
*/}}
{{- define "tech-radar.libretranslateUrl" -}}
{{- if .Values.libretranslate.enabled -}}
http://{{ .Values.libretranslate.name }}:{{ .Values.libretranslate.port }}
{{- end -}}
{{- end }}

{{/*
Uygulama Secret'inin adi (spec 6.1): secrets.existingSecret doluysa o (or. VSO'nun
yazdigi Secret), degilse chart'in kendi teknoloji-secret'i.
*/}}
{{- define "tech-radar.secretAdi" -}}
{{- .Values.secrets.existingSecret | default "teknoloji-secret" -}}
{{- end }}

{{/*
Migration Job adi (spec 6.1). helm: her revizyonda yeni ad (Job spec'i degistirilemez).
argocd: sabit ad; Argo CD `helm template` kullanir, .Release.Revision hep 1'dir ve Job
her senkronda Sync hook'u olarak yeniden olusturulur.
*/}}
{{- define "tech-radar.migrationJobAdi" -}}
{{- if eq .Values.migration.mode "argocd" -}}
{{ .Values.migration.name }}
{{- else if eq .Values.migration.mode "helm" -}}
{{ .Values.migration.name }}-r{{ .Release.Revision }}
{{- else -}}
{{- fail (printf "migration.mode 'helm' ya da 'argocd' olmali (gelen: %q)" .Values.migration.mode) -}}
{{- end -}}
{{- end }}

{{/*
Uygulama konteynerlerinin ortak ortami (api, worker, scheduler, migrate, migrasyon-bekle).
*/}}
{{- define "tech-radar.uygulamaOrtami" -}}
envFrom:
  - configMapRef:
      name: teknoloji-config
env:
  - name: SECRET_KEY
    valueFrom:
      secretKeyRef:
        name: {{ include "tech-radar.secretAdi" . }}
        key: SECRET_KEY
  - name: DB_USER
    valueFrom:
      secretKeyRef:
        name: {{ include "tech-radar.secretAdi" . }}
        key: DB_USER
  - name: DB_PASSWORD
    valueFrom:
      secretKeyRef:
        name: {{ include "tech-radar.secretAdi" . }}
        key: DB_PASSWORD
  - name: GEMINI_API_KEY
    valueFrom:
      secretKeyRef:
        name: {{ include "tech-radar.secretAdi" . }}
        key: GEMINI_API_KEY
  # optional: existingSecret (VSO) bu anahtarlari tasimiyorsa pod yine acilir (chart 2.2.0)
  - name: GITHUB_TOKEN
    valueFrom:
      secretKeyRef:
        name: {{ include "tech-radar.secretAdi" . }}
        key: GITHUB_TOKEN
        optional: true
  - name: NVD_API_KEY
    valueFrom:
      secretKeyRef:
        name: {{ include "tech-radar.secretAdi" . }}
        key: NVD_API_KEY
        optional: true
{{- end }}

{{/*
Pod sablonu annotation'lari: configmap/secret degisince pod'lar yeniden olusur.
secrets.existingSecret'te Secret chart'in disindadir; degisince pod'lari sahibi yeniden
baslatir (VSO rolloutRestartTargets), checksum/secret yazilmaz.
*/}}
{{- define "tech-radar.ayarOzeti" -}}
checksum/config: {{ include (print .Template.BasePath "/configmap.yaml") . | sha256sum }}
{{- if not .Values.secrets.existingSecret }}
checksum/secret: {{ include (print .Template.BasePath "/secret.yaml") . | sha256sum }}
{{- end }}
{{- end }}

{{/*
Migration'lar uygulanana kadar bekleyen initContainer (spec 7.6).
Cagiran: include "tech-radar.migrasyonBekle" . | nindent 8   (initContainers: altinda)
*/}}
{{- define "tech-radar.migrasyonBekle" -}}
- name: migrasyon-bekle
  image: {{ include "tech-radar.image" (dict "image" .Values.backend.image "root" .) }}
  imagePullPolicy: {{ .Values.backend.image.pullPolicy }}
  command:
    - sh
    - -c
    - |
      until python manage.py migrate --check >/dev/null 2>&1; do
        echo "Migration'lar bekleniyor ({{ include "tech-radar.migrationJobAdi" . }})..."
        sleep 5
      done
      echo "Migration'lar uygulanmis."
  securityContext:
    {{- include "tech-radar.containerSecurityContext" (dict "root" . "bilesen" .Values.backend) | nindent 4 }}
  {{- include "tech-radar.uygulamaOrtami" . | nindent 2 }}
  volumeMounts:
    - name: tmp
      mountPath: /tmp
  resources:
    {{- toYaml .Values.migration.resources | nindent 4 }}
{{- end }}
