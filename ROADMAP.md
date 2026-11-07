# HangarLLM — Visão, melhorias aplicadas e roadmap

> **One home for every AI model and agent.** HangarLLM é um gateway de LLMs e agentes open source, self-hosted e enterprise-ready, derivado do LiteLLM (MIT) a partir do commit `709b27e2` (v1.110.0).

## 1. Ponto de partida (diagnóstico do upstream)

| Métrica | Valor | Leitura |
|---|---|---|
| Código Python em `litellm/` | ~1,06 milhão de linhas | Base enorme; manutenção depende de modularização |
| `proxy/proxy_server.py` | 22.903 linhas | "God file": startup, rotas, config e jobs no mesmo módulo |
| `utils.py` / `main.py` | 12.039 / 9.660 linhas | Mesmo problema no SDK |
| Providers em `litellm/llms/` | 165 | Cobertura excelente, é o maior ativo |
| Modelos Prisma (tabelas) | 107 | Esquema amplo, prefixo `LiteLLM_` em todas |
| Arquivos de teste | 5.616 | Boa cobertura, mas lenta para CI |
| Pasta `enterprise/` | ~14,6 mil linhas sob licença **comercial** | Não pode ser copiada nem redistribuída |
| Gate de licença | `premium_user` + chamada a `license.litellm.ai` | Phone-home e features bloqueadas |
| Cost map de preços | Baixado do GitHub da BerriAI a cada boot | Risco de supply chain e boot não determinístico |

## 2. Decisões de arquitetura do fork

1. **Licença limpa.** Todo o repositório passa a ser MIT. A pasta `enterprise/` foi removida (licença comercial), e as features equivalentes foram **reimplementadas do zero** em `litellm/hangar/` (clean-room, sem consultar o código pago). Os créditos ficam no `NOTICE`.
2. **Namespace Python compatível.** O import continua `litellm`, então HangarLLM é um *drop-in replacement*: configs, SDKs, callbacks e integrações (Langfuse, OTel etc.) seguem funcionando. O pacote `hangarllm` é um alias (`import hangarllm`).
3. **Marca em tudo que o usuário vê:** CLI (`hangarllm`, `hangar`), UI, Docker, Helm, README, e-mails, Swagger e mensagens de erro.
4. **Compatibilidade de configuração.** Toda variável `HANGARLLM_*` espelha a `LITELLM_*` correspondente, e as `LITELLM_*` continuam valendo. Tabelas do banco, chaves de config e headers não foram renomeados, para permitir migrar um banco LiteLLM existente sem migração de dados.

## 3. Melhorias já aplicadas

| # | Melhoria | Onde |
|---|---|---|
| 1 | **Todas as features pagas liberadas** (SSO, audit log, guardrails enterprise, e-mails, PagerDuty, controles de callback, custom auth/SSO, custos de batch/responses, branding de docs etc.) | `litellm/hangar/`, `litellm/proxy/auth/litellm_license.py` |
| 2 | **Zero phone-home de licença**: nenhuma chamada a servidor de licença e nenhum limite de assentos ou de times | `litellm_license.py` |
| 3 | **Kill-switch por feature** `HANGARLLM_DISABLED_FEATURES=auto_router,...` para deploys enxutos ou regulados | `litellm_license.py` |
| 4 | **Preços embarcados por padrão**: o boot usa o cost map da release, sem baixar JSON remoto. Opt-in com `HANGARLLM_LOCAL_MODEL_COST_MAP=false` | `get_model_cost_map.py` |
| 5 | **Policy templates embarcados**: catálogo remoto só com `HANGARLLM_POLICY_TEMPLATES_URL` | `policy_endpoints/endpoints.py` |
| 6 | **Design system Hangar**: navy + âmbar, dark-first, contraste AA, logo vetorial, favicon, tela de login com o hero | `ui/litellm-dashboard` |
| 7 | **Um único sistema de ícones** (Lucide, licença ISC), com mapa central de ícones de navegação; `@heroicons` removido | `src/components/hangar/icons.ts` |
| 8 | **UI sem upsell**: banners "Enterprise", trial e upgrade removidos; nenhum gate visual | UI |
| 9 | **Aliases `HANGARLLM_*`** para todas as env vars e pacote `hangarllm` | `litellm/__init__.py`, `hangarllm/` |
| 10 | **Docker Compose de quickstart** com Postgres, Redis e Prometheus; imagens e Helm renomeados; CI próprio | `docker-compose.yml`, `helm/`, `.github/` |

### Lacunas conhecidas da reimplementação (a fechar primeiro)
- `CheckResponsesCost`: respostas em background são rastreadas, mas o custo ainda não é cobrado (hooks de billing vazios).
- `CheckBatchCost`: o preço vem do logging de custo de batch do core; falta teste contra provider real.
- Managed files: os fluxos principais funcionam (upload, retrieve, list, delete, content, batch, fine-tune, controle de acesso). Faltam casos de borda, como atraso no id do arquivo de saída e URLs de storage.
- Ainda não reimplementados: `/user/available_users` (contagem de assentos não se aplica), `/liteadmin/slack/connect` e as rotas extras de vector store.
- **Build da UI no Linux**: o `next build` (Next 16.4.1, Turbopack) quebra com "conflicting effects for the same key" em containers Linux. O código original do upstream nesse commit também quebra, e no Windows o build passa. Por isso o `docker compose` usa `UI_STAGE=ui-prebuilt`, que reaproveita o bundle versionado em `litellm/proxy/_experimental/out`. Dá para voltar ao build dentro da imagem (`HANGARLLM_UI_STAGE=ui-builder`) quando sair uma versão do Next com correção.
- **Dev local no Windows**: o pacote exige a extensão Rust `litellm.rust_bridge._native`. Sem o toolchain Rust (rustup + MSVC), rode via Docker. O fallback em Python puro está no P0.
- Revisar o redator de segredos: agora ele trata qualquer chave `*token*` como credencial (números puros, como `max_tokens`, ficam de fora).

### Skills Hub Git Sync (entregue)
- Conexão com GitHub ou GitHub Enterprise via GitHub App, token fine-grained ou repositório público. Escolha de repositório, branch e pasta.
- Sincronização por webhook (HMAC) com polling de reserva (ETag) e lock no banco para uma réplica por vez. Cada sync fica fixada no SHA do commit.
- Validação por skill com quarentena: manifesto, nomes duplicados, symlinks, binários, segredos, comandos perigosos e frases de prompt injection. Se uma skill que já estava no ar quebra, a última versão boa continua ativa.
- Escopo por grupo de acesso `git:<owner>/<repo>` ou para todas as chaves, modo automático ou com aprovação, rollback por commit e skills somente leitura no hub.
- Comunicação por banner na UI, relatório por commit e alerta `skill_sync_alerts`.
- Próximos passos: rodar o scanner externo (`skill_scanner`) dentro da sync, mostrar o diff entre commits na UI, adicionar GitLab e Bitbucket e enviar status check no PR ("skills válidas") antes do merge.

## 4. Roadmap priorizado

### P0 — fundação (próximas 2 a 4 semanas)
- **Quebrar `proxy_server.py`** em `app_factory.py`, `startup/` (config, DB, jobs), `routers/` (um por domínio) e `state.py` (estado global hoje espalhado em ~200 `global`s). Isso reduz o tempo de import, facilita testes e diminui conflitos com o upstream.
- **Sincronização com o upstream** via `git remote add upstream` + script `scripts/sync_upstream.sh`, que faz cherry-pick só de `litellm/llms/**` e do cost map. Assim os 165 providers ficam atualizados sem trazer código comercial.
- **Build nativo opcional**: fallback Python puro para `litellm.rust_bridge` quando a extensão Rust não está compilada. Hoje o pacote não importa sem o Rust, o que trava dev no Windows e instalação via `pip install -e`.
- **Suíte de testes "smoke"** (menos de 3 minutos) no CI: auth, chat completion mockado, criação de chave, spend log, guardrails Hangar.

### P1 — diferenciais de produto (alinhados à marca "Hangar")
- **Agent Hangar Registry**: catálogo unificado de agentes (A2A, MCP, ACP e OpenAI Assistants), com versionamento e promoção **stage → prod** (ícone "Stage → Prod" da marca). Cada agente vira uma "aeronave" com dono, orçamento, guardrails e traces.
- **Composição de agentes** ("Combine agents into new agents"): definir em YAML ou na UI um agente orquestrador que chama sub-agentes (Research, Analysis, Writing) via A2A, com custo agregado por árvore de chamadas.
- **Suporte a ACP** (Agent Communication Protocol) como terceiro protocolo de entrada, ao lado de OpenAI API, MCP e A2A.
- **Memória gerenciada** por chave, time ou agente (ícone "Memory"), com backend pgvector/Redis, TTL, export e política de retenção LGPD/GDPR.
- **Cost tracking em tempo real**: streaming de spend via SSE para o dashboard, alertas de anomalia (desvio-padrão por chave) e forecast de fim de mês.
- **Audit log imutável** com hash encadeado (tamper-evident), export para S3/GCS e SIEM (Splunk/Datadog) via OTel logs.

### P2 — operação enterprise
- **SSO completo**: OIDC + SAML + SCIM 2.0 com mapeamento de grupos para times e papéis, sem nenhum limite.
- **Multi-tenant real**: organizações isoladas por schema do Postgres ou por Row-Level Security.
- **Helm "production profile"**: HPA, PDB, NetworkPolicy, read-only root FS, secrets via External Secrets Operator; guias para GKE, AKS e EKS (como na arte de marca).
- **Observabilidade padrão**: dashboard Grafana "Hangar Control Tower" versionado no repo, com SLOs de latência p95 e taxa de fallback por provider.
- **i18n pt-BR** completo na UI (a infraestrutura i18next já existe).
- **Renomear tabelas `LiteLLM_*` → `Hangar_*`** com migração reversível, só depois de existir ferramenta de migração automática e quando a compatibilidade com bancos LiteLLM deixar de ser prioridade.

## 5. Riscos e cuidados
- **Marca**: "LiteLLM" é nome e marca da BerriAI. Mantemos o crédito no `NOTICE` e evitamos o nome em qualquer superfície de produto.
- **Logos de providers** (OpenAI, Anthropic etc.) são marcas de terceiros. Usamos só para identificar integrações (uso nominativo).
- **Divergência do upstream**: quanto mais refatorarmos `proxy/`, mais caro fica fazer merge. Por isso a estratégia de sync é seletiva (providers e preços).
