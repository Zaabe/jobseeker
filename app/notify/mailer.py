"""Invio delle notifiche via email.

Usa smtplib della libreria standard: nessuna dipendenza aggiuntiva e nessun
servizio esterno a cui affidare i dati. La configurazione sta nel file .env.
"""
from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, formatdate
from typing import Any

from ..config import SECRETS


class MailError(RuntimeError):
    """Configurazione mancante o invio fallito."""


def smtp_config() -> dict[str, Any]:
    return {
        "host": SECRETS.get("smtp_host", "").strip(),
        "port": int(SECRETS.get("smtp_port") or 587),
        "user": SECRETS.get("smtp_user", "").strip(),
        "password": SECRETS.get("smtp_password", ""),
        "sender": (SECRETS.get("smtp_from") or SECRETS.get("smtp_user", "")).strip(),
        "use_tls": str(SECRETS.get("smtp_use_tls", "true")).lower() in ("true", "1", "yes", "on"),
    }


def is_configured() -> bool:
    config = smtp_config()
    return bool(config["host"] and config["sender"])


def send_email(to: str, subject: str, html_body: str, text_body: str) -> None:
    """Invia un messaggio. Solleva MailError con un motivo leggibile se fallisce."""
    config = smtp_config()
    if not config["host"]:
        raise MailError("SMTP_HOST non configurato nel file .env")
    if not config["sender"]:
        raise MailError("SMTP_FROM (o SMTP_USER) non configurato nel file .env")
    if not to:
        raise MailError("nessun destinatario impostato")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr(("JobSeeker", config["sender"]))
    message["To"] = to
    message["Date"] = formatdate(localtime=True)
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    try:
        if config["port"] == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(config["host"], config["port"], context=context, timeout=30) as server:
                if config["user"]:
                    server.login(config["user"], config["password"])
                server.send_message(message)
        else:
            with smtplib.SMTP(config["host"], config["port"], timeout=30) as server:
                server.ehlo()
                if config["use_tls"]:
                    server.starttls(context=ssl.create_default_context())
                    server.ehlo()
                if config["user"]:
                    server.login(config["user"], config["password"])
                server.send_message(message)
    except smtplib.SMTPAuthenticationError as exc:
        raise MailError(
            "autenticazione SMTP rifiutata. Con Gmail serve una password per le app, "
            f"non quella dell'account. Dettaglio: {exc.smtp_error.decode(errors='replace')[:120]}"
        ) from exc
    except (smtplib.SMTPException, OSError, ssl.SSLError) as exc:
        raise MailError(f"invio fallito: {type(exc).__name__}: {str(exc)[:160]}") from exc


# --------------------------------------------------------------------------
# Composizione del messaggio
# --------------------------------------------------------------------------

def _fmt_salary(job: dict[str, Any]) -> str:
    low, high, currency = job.get("salary_min"), job.get("salary_max"), job.get("currency") or ""
    if not low and not high:
        return ""
    if low and high:
        return f"{low:,.0f} - {high:,.0f} {currency}".replace(",", ".")
    return f"{(low or high):,.0f} {currency}".replace(",", ".")


def render_digest(items: list[dict[str, Any]], threshold: int) -> tuple[str, str, str]:
    """Compone oggetto, corpo HTML e corpo testuale per un gruppo di offerte.

    Ogni voce e' un dizionario con le chiavi `job`, `score` e `breakdown`.
    """
    count = len(items)
    if count == 1:
        job = items[0]["job"]
        subject = f"[JobSeeker] {items[0]['score']:.0f}% - {job['title']} @ {job['company']}"
    else:
        best = max(i["score"] for i in items)
        subject = f"[JobSeeker] {count} nuove offerte compatibili (fino al {best:.0f}%)"

    rows_html: list[str] = []
    lines_text: list[str] = []
    for item in items:
        job, score = item["job"], item["score"]
        breakdown = item.get("breakdown") or {}
        matched = breakdown.get("matched_skills") or []
        missing = breakdown.get("missing_skills") or []
        salary = _fmt_salary(job)
        location = job.get("location") or job.get("city") or "sede non indicata"
        if job.get("remote"):
            location += " - da remoto"

        colour = "#1a7f37" if score >= 70 else ("#9a6700" if score >= 50 else "#57606a")
        rows_html.append(f"""
      <tr><td style="padding:18px 0;border-bottom:1px solid #e6e8eb;">
        <div style="font-size:13px;color:{colour};font-weight:700;letter-spacing:.02em;">
          COMPATIBILITA' {score:.0f}%
        </div>
        <div style="font-size:17px;font-weight:600;margin:6px 0 2px;">
          <a href="{job.get('url', '')}" style="color:#0b3d91;text-decoration:none;">{_esc(job['title'])}</a>
        </div>
        <div style="font-size:14px;color:#57606a;">
          {_esc(job.get('company', ''))} &middot; {_esc(location)}{' &middot; ' + _esc(salary) if salary else ''}
        </div>
        {_skill_line('Competenze in comune', matched, '#1a7f37')}
        {_skill_line('Richieste non rilevate', missing, '#8b5cf6')}
        <div style="margin-top:10px;">
          <a href="{job.get('url', '')}"
             style="display:inline-block;background:#0b3d91;color:#fff;text-decoration:none;
                    padding:8px 16px;border-radius:6px;font-size:14px;">Vedi l'offerta</a>
        </div>
      </td></tr>""")

        lines_text.append(
            f"[{score:.0f}%] {job['title']} @ {job.get('company', '')}\n"
            f"     {location}{' - ' + salary if salary else ''}\n"
            f"     {job.get('url', '')}\n"
            + (f"     competenze in comune: {', '.join(matched[:8])}\n" if matched else "")
            + (f"     richieste non rilevate: {', '.join(missing[:8])}\n" if missing else "")
        )

    html = f"""<!doctype html>
<html><body style="margin:0;padding:24px;background:#f6f8fa;
   font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#1f2328;">
  <table role="presentation" width="100%" style="max-width:620px;margin:0 auto;background:#fff;
         border-radius:10px;padding:28px;border:1px solid #e6e8eb;">
    <tr><td>
      <div style="font-size:20px;font-weight:700;">
        {count} nuova offerta compatibile{'' if count == 1 else 'e'}
      </div>
      <div style="font-size:14px;color:#57606a;margin-top:4px;">
        Sopra la soglia del {threshold}% che hai impostato.
      </div>
    </td></tr>
    {''.join(rows_html)}
    <tr><td style="padding-top:18px;font-size:12px;color:#8b949e;">
      Messaggio generato da JobSeeker sul tuo computer. Per non riceverlo piu',
      disattiva le notifiche email dalle impostazioni dell'applicazione.
    </td></tr>
  </table>
</body></html>"""

    text = (
        f"{count} nuova offerta compatibile (soglia {threshold}%)\n"
        + "=" * 58 + "\n\n" + "\n".join(lines_text)
        + "\nGenerato da JobSeeker.\n"
    )
    return subject, html, text


def _esc(value: Any) -> str:
    return (
        str(value or "")
        .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def _skill_line(label: str, skills: list[str], colour: str) -> str:
    if not skills:
        return ""
    shown = ", ".join(_esc(s) for s in skills[:6])
    extra = f" +{len(skills) - 6}" if len(skills) > 6 else ""
    return (
        f'<div style="font-size:13px;color:#57606a;margin-top:6px;">'
        f'<span style="color:{colour};font-weight:600;">{label}:</span> {shown}{extra}</div>'
    )
