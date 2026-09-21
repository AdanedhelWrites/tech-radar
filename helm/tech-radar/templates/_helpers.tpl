{{/*
Expand the name of the chart.
*/}}
{{- define "tech-radar.name" -}}
{{- default .Chart.Name .Values.global.appName | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "tech-radar.fullname" -}}
{{- .Values.global.appName | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "tech-radar.labels" -}}
app.kubernetes.io/part-of: {{ .Values.global.labels.partOf }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
{{- end }}

{{/*
Selector labels for a component
*/}}
{{- define "tech-radar.selectorLabels" -}}
app.kubernetes.io/name: {{ .name }}
{{- end }}

{{/*
Backend image
*/}}
{{- define "tech-radar.backendImage" -}}
{{ .Values.backend.image.repository }}:{{ .Values.backend.image.tag }}
{{- end }}

{{/*
Frontend image
*/}}
{{- define "tech-radar.frontendImage" -}}
{{ .Values.frontend.image.repository }}:{{ .Values.frontend.image.tag }}
{{- end }}

{{/*
Pod guvenlik baglami — non-root calismayi zorunlu kilar. UID/GID taban
imajin kendi kullanicisidir (bkz. values.yaml'daki ilgili securityContext).
Cagiran: include "tech-radar.podSecurityContext" .Values.<bilesen>.securityContext
*/}}
{{- define "tech-radar.podSecurityContext" -}}
runAsNonRoot: true
runAsUser: {{ .runAsUser }}
runAsGroup: {{ .runAsGroup }}
seccompProfile:
  type: RuntimeDefault
{{- end }}

{{/*
Container guvenlik baglami — tum bilesenlerde ayni: ayricalik yukseltme,
fazla capability ve yazilabilir kok dosya sistemi kapali. Deger
global.containerSecurityContext'ten gelir, sablona sabit yazilmaz.
*/}}
{{- define "tech-radar.containerSecurityContext" -}}
{{ toYaml .Values.global.containerSecurityContext }}
{{- end }}
