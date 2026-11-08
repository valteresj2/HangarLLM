"""
HangarLLM email templates.

One table-based, inline-styled layout (renders in Outlook, Gmail and Apple Mail)
in the Hangar palette: navy ``#0F172A`` frame, amber ``#F5B301`` accent.
Every interpolated value is HTML-escaped.
"""

from html import escape
from typing import Final

NAVY: Final = "#0F172A"
NAVY_SOFT: Final = "#1E293B"
AMBER: Final = "#F5B301"
TEXT: Final = "#0F172A"
MUTED: Final = "#64748B"
SURFACE: Final = "#F8FAFC"

# Inline SVG hangar mark (most clients fall back to the alt text / logo URL row)
_HANGAR_MARK: Final = (
    '<svg width="36" height="36" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" '
    'style="vertical-align:middle"><path d="M8 28 L32 15 L56 28 V52 H44 V34 H20 V52 H8 Z" '
    f'fill="none" stroke="{AMBER}" stroke-width="5" stroke-linejoin="round"/></svg>'
)


def _logo(logo_url: str | None) -> str:
    if logo_url:
        return f'<img src="{escape(logo_url)}" alt="HangarLLM" height="36" style="vertical-align:middle;border:0">'
    return _HANGAR_MARK


def render_layout(
    *,
    title: str,
    preheader: str,
    body_html: str,
    logo_url: str | None,
    support_contact: str,
    cta_label: str | None = None,
    cta_url: str | None = None,
) -> str:
    cta: Final = (
        f'<tr><td style="padding:8px 40px 32px 40px"><a href="{escape(cta_url)}" '
        f'style="display:inline-block;background:{AMBER};color:{NAVY};font-weight:700;'
        f'text-decoration:none;padding:12px 22px;border-radius:8px">{escape(cta_label)}</a></td></tr>'
        if cta_label and cta_url
        else ""
    )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escape(title)}</title></head>
<body style="margin:0;padding:0;background:{SURFACE};font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:{TEXT}">
<span style="display:none;max-height:0;overflow:hidden">{escape(preheader)}</span>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:{SURFACE};padding:24px 0">
<tr><td align="center">
<table role="presentation" width="560" cellspacing="0" cellpadding="0" style="max-width:560px;width:100%;background:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #E2E8F0">
<tr><td style="background:{NAVY};padding:20px 40px">{_logo(logo_url)}
<span style="color:#ffffff;font-size:18px;font-weight:700;vertical-align:middle;margin-left:10px">Hangar<span style="color:{AMBER}">LLM</span></span></td></tr>
<tr><td style="height:4px;background:{AMBER};line-height:4px;font-size:0">&nbsp;</td></tr>
<tr><td style="padding:32px 40px 8px 40px"><h1 style="margin:0 0 16px 0;font-size:22px;color:{NAVY}">{escape(title)}</h1>{body_html}</td></tr>
{cta}
<tr><td style="padding:20px 40px;background:{NAVY_SOFT};color:#CBD5E1;font-size:12px;line-height:1.6">
Sent by your HangarLLM gateway &middot; one home for every AI model and agent.<br>
Questions? Contact <a href="mailto:{escape(support_contact)}" style="color:{AMBER}">{escape(support_contact)}</a>.
</td></tr>
</table></td></tr></table></body></html>"""


def _p(text: str) -> str:
    return f'<p style="margin:0 0 16px 0;font-size:15px;line-height:1.6">{text}</p>'


def _kv_table(rows: list[tuple[str, str]]) -> str:
    cells: Final = "".join(
        f'<tr><td style="padding:8px 12px;color:{MUTED};font-size:13px;border-bottom:1px solid #E2E8F0">{escape(k)}</td>'
        f'<td style="padding:8px 12px;font-size:13px;font-weight:600;border-bottom:1px solid #E2E8F0">{escape(v)}</td></tr>'
        for k, v in rows
    )
    return (
        f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
        f'style="border:1px solid #E2E8F0;border-radius:8px;margin:0 0 20px 0">{cells}</table>'
    )


def _key_box(label: str, key: str) -> str:
    return (
        f'<p style="margin:0 0 6px 0;font-size:13px;color:{MUTED}">{escape(label)}</p>'
        f'<div style="background:{NAVY};color:{AMBER};font-family:ui-monospace,Menlo,Consolas,monospace;'
        f'font-size:14px;padding:14px 16px;border-radius:8px;word-break:break-all;margin:0 0 20px 0">{escape(key)}</div>'
    )


def _money(value: float | None) -> str:
    return "No limit" if value is None else f"${value:,.2f}"


def key_created_email(
    *,
    recipient: str,
    key: str,
    max_budget: float | None,
    key_alias: str | None,
    base_url: str,
    logo_url: str | None,
    support: str,
) -> tuple[str, str]:
    body: Final = (
        _p(f"Hi {escape(recipient)}, a new virtual key was created for you on HangarLLM.")
        + _key_box("Your API key (store it safely - it is shown only once)", key)
        + _kv_table([("Key alias", key_alias or "-"), ("Budget", _money(max_budget)), ("Gateway", base_url)])
        + _p(
            "Use it with any OpenAI-compatible SDK by pointing <code>base_url</code> at the gateway "
            "and passing the key as the API key."
        )
    )
    subject: Final = "HangarLLM: your API key is ready"
    return subject, render_layout(
        title="Your API key is ready",
        preheader="A new HangarLLM virtual key was created for you",
        body_html=body,
        logo_url=logo_url,
        support_contact=support,
        cta_label="Open the HangarLLM console",
        cta_url=f"{base_url.rstrip('/')}/ui",
    )


def key_rotated_email(
    *, recipient: str, key: str, key_alias: str | None, base_url: str, logo_url: str | None, support: str
) -> tuple[str, str]:
    body: Final = (
        _p(f"Hi {escape(recipient)}, your virtual key <b>{escape(key_alias or '-')}</b> was rotated.")
        + _key_box("New API key", key)
        + _p("The previous key stops working at the end of its grace period. Update your applications now.")
    )
    return "HangarLLM: your API key was rotated", render_layout(
        title="Your API key was rotated",
        preheader="Update your applications with the new key",
        body_html=body,
        logo_url=logo_url,
        support_contact=support,
        cta_label="Review keys",
        cta_url=f"{base_url.rstrip('/')}/ui",
    )


def user_invitation_email(
    *, recipient: str, team_name: str, invitation_link: str, logo_url: str | None, support: str
) -> tuple[str, str]:
    body: Final = (
        _p(f"Hi {escape(recipient)},")
        + _p(
            f"You have been invited to <b>{escape(team_name)}</b> on HangarLLM - the gateway your team uses "
            "to reach every AI model and agent with one key, one bill and one audit trail."
        )
        + _p("Accept the invitation to set your password and create your first key.")
    )
    return "You're invited to HangarLLM", render_layout(
        title="You're invited to HangarLLM",
        preheader=f"Join {team_name} on HangarLLM",
        body_html=body,
        logo_url=logo_url,
        support_contact=support,
        cta_label="Accept invitation",
        cta_url=invitation_link,
    )


def budget_alert_email(
    *,
    recipient: str,
    alert_title: str,
    entity: str,
    spend: float,
    budget: float | None,
    base_url: str,
    logo_url: str | None,
    support: str,
) -> tuple[str, str]:
    pct: Final = f"{(spend / budget * 100):.0f}%" if budget else "-"
    body: Final = (
        _p(f"Hi {escape(recipient)}, {escape(entity)} has reached a budget threshold.")
        + _kv_table([("Current spend", _money(spend)), ("Budget", _money(budget)), ("Used", pct)])
        + _p("Requests may be blocked once the hard budget is reached. Raise the budget or reduce usage.")
    )
    return f"HangarLLM: {alert_title}", render_layout(
        title=alert_title,
        preheader=f"{entity} spend is {_money(spend)}",
        body_html=body,
        logo_url=logo_url,
        support_contact=support,
        cta_label="View usage",
        cta_url=f"{base_url.rstrip('/')}/ui/usage",
    )
