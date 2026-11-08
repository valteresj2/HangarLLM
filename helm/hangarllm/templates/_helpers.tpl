{{/*
Expand the name of the chart.
*/}}
{{- define "hangarllm.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "hangarllm.fullname" -}}
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
{{- define "hangarllm.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "hangarllm.labels" -}}
helm.sh/chart: {{ include "hangarllm.chart" . }}
{{ include "hangarllm.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "hangarllm.selectorLabels" -}}
app.kubernetes.io/name: {{ include "hangarllm.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "hangarllm.billingMetricsEnv" -}}
- name: HANGARLLM_BILLING_METRICS_ENDPOINT
  value: {{ required "billingMetrics.endpoint is required when billingMetrics.enabled is true" .Values.billingMetrics.endpoint | quote }}
- name: HANGARLLM_BILLING_METRICS_TOKEN_URL
  value: {{ required "billingMetrics.tokenUrl is required when billingMetrics.enabled is true" .Values.billingMetrics.tokenUrl | quote }}
- name: HANGARLLM_BILLING_METRICS_CLIENT_ID
  valueFrom:
    secretKeyRef:
      name: {{ required "billingMetrics.secretName is required when billingMetrics.enabled is true" .Values.billingMetrics.secretName }}
      key: client-id
- name: HANGARLLM_BILLING_METRICS_CLIENT_SECRET
  valueFrom:
    secretKeyRef:
      name: {{ required "billingMetrics.secretName is required when billingMetrics.enabled is true" .Values.billingMetrics.secretName }}
      key: client-secret
{{- with .Values.billingMetrics.exportIntervalMs }}
- name: HANGARLLM_BILLING_METRICS_EXPORT_INTERVAL_MS
  value: {{ . | quote }}
{{- end }}
{{- end -}}

{{/*
Create the name of the service account to use
*/}}
{{- define "hangarllm.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "hangarllm.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create the service account name used by migration jobs.
When Helm hooks are enabled, pre-install/pre-upgrade hooks run before normal resources.
If this chart is creating the ServiceAccount, it is not yet available for the hook job,
so fall back to "default" (or an explicit override) to avoid a cyclic dependency.
*/}}
{{- define "hangarllm.migrationServiceAccountName" -}}
{{- if and .Values.migrationJob.hooks.helm.enabled .Values.serviceAccount.create }}
{{- default "default" .Values.migrationJob.serviceAccountName }}
{{- else }}
{{- include "hangarllm.serviceAccountName" . }}
{{- end }}
{{- end }}

{{/*
Get redis service name.
The bundled Redis subchart only serves sentinel in "replication" architecture
(it rejects standalone + sentinel outright), and in that mode the sentinel
Service is named "<release>-redis", not "<release>-redis-master".
*/}}
{{- define "hangarllm.redis.serviceName" -}}
{{- if .Values.redis.sentinel.enabled -}}
{{- printf "%s-%s" .Release.Name (default "redis" .Values.redis.nameOverride | trunc 63 | trimSuffix "-") -}}
{{- else -}}
{{- printf "%s-%s-master" .Release.Name (default "redis" .Values.redis.nameOverride | trunc 63 | trimSuffix "-") -}}
{{- end -}}
{{- end -}}

{{/*
Get redis service port
*/}}
{{- define "hangarllm.redis.port" -}}
{{- if .Values.redis.sentinel.enabled -}}
{{ .Values.redis.sentinel.service.ports.sentinel }}
{{- else -}}
{{ .Values.redis.master.service.ports.redis }}
{{- end -}}
{{- end -}}

{{/*
Reject an unpinned image tag for the bundled PostgreSQL.
A floating tag lets a chart upgrade start a newer PostgreSQL major against the
existing PersistentVolumeClaim. The server then refuses to start on a data
directory written by another major version, and the only way back is a dump
taken before the change, which by that point no longer exists.
*/}}
{{- define "hangarllm.validateBundledPostgresImageTag" -}}
{{- $tag := .Values.postgresql.image.tag | default "" | toString -}}
{{- $digest := .Values.postgresql.image.digest | default "" | toString -}}
{{- if and (eq $digest "") (or (eq $tag "") (eq $tag "latest")) -}}
{{- fail (printf "postgresql.image.tag must be pinned to an explicit version when db.deployStandalone is true (got %q). An unpinned tag can start a different PostgreSQL major against the existing data directory, which makes the database unreadable and is not recoverable in place. Crossing a major version requires a dump and restore." $tag) -}}
{{- end -}}
{{- end -}}

{{/*
Whether the existing Postgres is reached with a short-lived token (AWS RDS IAM
or Microsoft Entra ID) instead of a password.
*/}}
{{- define "hangarllm.db.tokenAuth" -}}
{{- if or .Values.db.useIAMAuth .Values.db.useAzureEntraAuth -}}true{{- end -}}
{{- end -}}

{{- define "hangarllm.validateDbTokenAuth" -}}
{{- if and .Values.db.useIAMAuth .Values.db.useAzureEntraAuth -}}
{{- fail "db.useIAMAuth and db.useAzureEntraAuth are mutually exclusive: the database password can only come from one token source" -}}
{{- end -}}
{{- if and (include "hangarllm.db.tokenAuth" .) (or (not .Values.db.useExisting) .Values.db.deployStandalone) -}}
{{- fail "db.useIAMAuth and db.useAzureEntraAuth need db.useExisting: true and db.deployStandalone: false (token auth targets an existing RDS or Azure Database for PostgreSQL; the bundled postgresql subchart only supports password auth)" -}}
{{- end -}}
{{- end -}}

{{/*
Database env for an existing Postgres, shared by the proxy container, the
collector sidecar and the migrations Job. Under token auth every entrypoint
mints its own token and assembles DATABASE_URL itself, so db.url is left out.
*/}}
{{- define "hangarllm.existingDbEnv" -}}
{{- $tokenAuth := include "hangarllm.db.tokenAuth" . -}}
- name: DATABASE_USERNAME
  {{- if .Values.db.username }}
  value: {{ .Values.db.username | quote }}
  {{- else }}
  valueFrom:
    secretKeyRef:
      name: {{ .Values.db.secret.name }}
      key: {{ .Values.db.secret.usernameKey }}
  {{- end }}
{{- if .Values.db.useIAMAuth }}
- name: IAM_TOKEN_DB_AUTH
  value: "true"
{{- else if .Values.db.useAzureEntraAuth }}
- name: AZURE_POSTGRESQL_AUTH
  value: "true"
{{- else }}
- name: DATABASE_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ .Values.db.secret.name }}
      key: {{ .Values.db.secret.passwordKey }}
{{- end }}
- name: DATABASE_HOST
  {{- if .Values.db.secret.endpointKey }}
  valueFrom:
    secretKeyRef:
      name: {{ .Values.db.secret.name }}
      key: {{ .Values.db.secret.endpointKey }}
  {{- else }}
  value: {{ .Values.db.endpoint }}
  {{- end }}
{{- if $tokenAuth }}
- name: DATABASE_PORT
  value: {{ .Values.db.port | quote }}
{{- end }}
- name: DATABASE_NAME
  value: {{ .Values.db.database }}
{{- if and $tokenAuth .Values.db.schema }}
- name: DATABASE_SCHEMA
  value: {{ .Values.db.schema | quote }}
{{- end }}
{{- if not $tokenAuth }}
- name: DATABASE_URL
  value: {{ .Values.db.url | quote }}
{{- end }}
{{- end -}}

{{/*
Environment shared by the proxy container and the opt-in collector sidecar:
database, pgbouncer, master key, redis, user envVars. Both containers must see
the same DATABASE_URL and REDIS_* so the sidecar reaches the pod's pgbouncer
and the same spend transaction buffer.
*/}}
{{- define "hangarllm.proxyEnv" -}}
{{- include "hangarllm.validateDbTokenAuth" . -}}
- name: HOST
  value: "{{ .Values.listen | default "0.0.0.0" }}"
- name: PORT
  value: {{ .Values.service.port | quote}}
{{- if .Values.db.deployStandalone }}
- name: DATABASE_USERNAME
  valueFrom:
    secretKeyRef:
      name: {{ include "hangarllm.fullname" . }}-dbcredentials
      key: username
- name: DATABASE_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "hangarllm.fullname" . }}-dbcredentials
      key: password
- name: DATABASE_HOST
  value: {{ .Release.Name }}-postgresql
- name: DATABASE_NAME
  value: hangarllm
{{- else if .Values.db.useExisting }}
{{ include "hangarllm.existingDbEnv" . }}
{{- end }}
{{- if and .Values.db.useExisting .Values.db.readReplicaUrl .Values.db.secret.readReplicaEndpointKey (not .Values.db.secret.readReplicaUrlKey) }}
- name: DATABASE_READER_HOST
  valueFrom:
    secretKeyRef:
      name: {{ .Values.db.secret.name }}
      key: {{ .Values.db.secret.readReplicaEndpointKey }}
{{- end }}
{{- if and .Values.db.useExisting .Values.db.secret.readReplicaUrlKey }}
- name: DATABASE_URL_READ_REPLICA
  valueFrom:
    secretKeyRef:
      name: {{ .Values.db.secret.name }}
      key: {{ .Values.db.secret.readReplicaUrlKey }}
{{- else if .Values.db.readReplicaUrl }}
- name: DATABASE_URL_READ_REPLICA
  value: {{ .Values.db.readReplicaUrl | quote }}
{{- end }}
{{- if .Values.db.connectionPool.enabled }}
- name: HANGARLLM_PGBOUNCER_ENABLED
  value: "true"
- name: HANGARLLM_PGBOUNCER_MAX_DB_CONNECTIONS
  value: {{ .Values.db.connectionPool.maxDbConnections | quote }}
- name: HANGARLLM_PGBOUNCER_MAX_CLIENT_CONN
  value: {{ .Values.db.connectionPool.maxClientConn | quote }}
{{- end }}
- name: PROXY_MASTER_KEY
  valueFrom:
    secretKeyRef:
      name: {{ .Values.masterkeySecretName | default (printf "%s-masterkey" (include "hangarllm.fullname" .)) }}
      key: {{ .Values.masterkeySecretKey | default "masterkey" }}
{{- if .Values.redis.enabled }}
- name: REDIS_HOST
  value: {{ include "hangarllm.redis.serviceName" . }}
- name: REDIS_PORT
  value: {{ include "hangarllm.redis.port" . | quote }}
- name: REDIS_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "redis.secretName" .Subcharts.redis }}
      key: {{include "redis.secretPasswordKey" .Subcharts.redis }}
{{- end }}
{{- /*
  Inject HANGARLLM_LOG only when envVars does not already define it.
*/}}
{{- if and .Values.logLevel (not (hasKey (default dict .Values.envVars) "HANGARLLM_LOG")) }}
- name: HANGARLLM_LOG
  value: {{ .Values.logLevel | quote }}
{{- end }}
{{- if .Values.envVars }}
{{- range $key, $val := .Values.envVars }}
- name: {{ $key }}
  value: {{ $val | quote }}
{{- end }}
{{- end }}
{{- with .Values.extraEnvVars }}
{{ toYaml . }}
{{- end }}
{{- if .Values.migrationJob.enabled }}
# Schema updates are owned by the dedicated migrations Job; skip
# the proxy's startup `prisma db push` so N replicas don't race
# one DB on every rollout. Placed last (after envVars and
# extraEnvVars) so this override can't be silently shadowed by a
# user-supplied DISABLE_SCHEMA_UPDATE under last-wins duplicate-env
# semantics — same pattern the migrations Job uses.
- name: DISABLE_SCHEMA_UPDATE
  value: "true"
{{- end }}
{{- end -}}

{{/*
Proxy-only metering and metrics env. The collector sidecar serves no HTTP
traffic, so it gets neither.
*/}}
{{- define "hangarllm.proxyMetricsEnv" -}}
{{- if .Values.billingMetrics.enabled }}
{{ include "hangarllm.billingMetricsEnv" . }}
{{- end }}
{{- if .Values.metricsServer.enabled }}
{{- if eq (int .Values.metricsServer.port) (int .Values.service.port) }}
{{- fail "metricsServer.port must differ from service.port" }}
{{- end }}
- name: PROMETHEUS_METRICS_PORT
  value: {{ .Values.metricsServer.port | quote }}
{{- end }}
{{- end -}}

{{/*
Directory of the collector's unix socket, shared between the two containers
through an emptyDir. Empty when the sidecar is off or uses 127.0.0.1 TCP.
*/}}
{{- define "hangarllm.collector.socketDir" -}}
{{- if and .Values.collector.enabled (hasPrefix "unix://" .Values.collector.address) -}}
{{- dir (trimPrefix "unix://" .Values.collector.address) -}}
{{- end -}}
{{- end -}}

{{- define "hangarllm.collectorEnv" -}}
- name: HANGARLLM_COLLECTOR_ENABLED
  value: "true"
- name: HANGARLLM_COLLECTOR_ADDRESS
  value: {{ .Values.collector.address | quote }}
- name: HANGARLLM_COLLECTOR_BUFFER_SIZE
  value: {{ .Values.collector.bufferSize | quote }}
- name: HANGARLLM_COLLECTOR_ON_UNAVAILABLE
  value: {{ .Values.collector.onUnavailable | quote }}
- name: HANGARLLM_COLLECTOR_DRAIN_TIMEOUT_SECONDS
  value: {{ .Values.collector.drainTimeoutSeconds | quote }}
{{- end -}}

{{- define "hangarllm.gateway.collectorSocketDir" -}}
{{- if and .Values.gateway.collector.enabled (hasPrefix "unix://" .Values.gateway.collector.address) -}}
{{- dir (trimPrefix "unix://" .Values.gateway.collector.address) -}}
{{- end -}}
{{- end -}}

{{/*
HANGARLLM_COLLECTOR_* env shared by the producer (gateway container) and the
consumer (collector container), so both agree on the transport and the
shutdown drain window.
*/}}
{{- define "hangarllm.gateway.collectorEnv" -}}
{{- with .Values.gateway.collector }}
- name: HANGARLLM_COLLECTOR_ENABLED
  value: "true"
- name: HANGARLLM_COLLECTOR_ADDRESS
  value: {{ .address | quote }}
- name: HANGARLLM_COLLECTOR_BUFFER_SIZE
  value: {{ .bufferSize | quote }}
- name: HANGARLLM_COLLECTOR_ON_UNAVAILABLE
  value: {{ .onUnavailable | quote }}
- name: HANGARLLM_COLLECTOR_DRAIN_TIMEOUT_SECONDS
  value: {{ .drainTimeoutSeconds | quote }}
{{- end }}
{{- end -}}

{{- define "hangarllm.lensConnectionEnv" -}}
{{- with .Values.lensWorker }}
{{- if or .enabled (and .mode (ne .mode "disabled")) }}
{{- fail "lensWorker was removed; deploy Lens from its own chart and set lens.* instead, see the chart README" }}
{{- end }}
{{- end }}
{{- with .Values.lens }}
{{- if .enabled }}
- name: HANGARLLM_LENS_URL
  value: {{ required "lens.url is required when lens.enabled is true" .url | quote }}
- name: HANGARLLM_LENS_PUBLIC_URL
  value: {{ required "lens.publicUrl is required when lens.enabled is true" .publicUrl | quote }}
- name: LENS_GATEWAY_SECRET
  valueFrom:
    secretKeyRef:
      name: {{ required "lens.gatewaySecret.name is required when lens.enabled is true" .gatewaySecret.name | quote }}
      key: {{ .gatewaySecret.key | quote }}
- name: HANGARLLM_LENS_SERVICE_TOKEN
  valueFrom:
    secretKeyRef:
      name: {{ required "lens.serviceTokenSecret.name is required when lens.enabled is true" .serviceTokenSecret.name | quote }}
      key: {{ .serviceTokenSecret.key | quote }}
{{- end }}
{{- end }}
{{- end -}}
