{{/*
=============================================================================
OmniEngine — Helm Template Helpers
=============================================================================
*/}}

{{/*
Expand the name of the chart.
*/}}
{{- define "omniengine.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because Kubernetes name fields are limited to this.
*/}}
{{- define "omniengine.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "omniengine.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels applied to all resources.
*/}}
{{- define "omniengine.labels" -}}
helm.sh/chart: {{ include "omniengine.chart" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/part-of: omniengine
{{- end }}

{{/*
Backend selector labels.
*/}}
{{- define "omniengine.backend.selectorLabels" -}}
app.kubernetes.io/name: {{ include "omniengine.name" . }}-backend
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: backend
{{- end }}

{{/*
Frontend selector labels.
*/}}
{{- define "omniengine.frontend.selectorLabels" -}}
app.kubernetes.io/name: {{ include "omniengine.name" . }}-frontend
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: frontend
{{- end }}

{{/*
Construct the DATABASE_URL from components.
*/}}
{{- define "omniengine.databaseUrl" -}}
postgresql+asyncpg://{{ .Values.postgresql.username }}:$(POSTGRES_PASSWORD)@{{ .Values.postgresql.host }}:{{ .Values.postgresql.port }}/{{ .Values.postgresql.database }}
{{- end }}

{{/*
Construct the REDIS_URL from components.
*/}}
{{- define "omniengine.redisUrl" -}}
redis://{{ .Values.redis.host }}:{{ .Values.redis.port }}/{{ .Values.redis.db }}
{{- end }}
