"""
HangarLLM open-core extensions.

Everything in this package is original, MIT-licensed HangarLLM code. It provides
the capabilities that upstream LiteLLM shipped only in its commercially-licensed
``enterprise`` package (email notifications, PagerDuty alerting, per-request
callback controls, moderation / secret-detection guardrails, route toggles,
custom auth / SSO hooks, audit-log and email-settings endpoints, managed files,
background cost reconciliation for batches and background responses, ...).

Layout
------
``litellm.hangar.callbacks``   logging-side controls and alerting (PagerDuty)
``litellm.hangar.emails``      transactional email loggers + settings endpoints
``litellm.hangar.guardrails``  moderation / content-safety guardrails
``litellm.hangar.proxy``       proxy-side hooks, routers and background jobs
"""

HANGAR_EXTENSIONS_VERSION = "1.0.0"
