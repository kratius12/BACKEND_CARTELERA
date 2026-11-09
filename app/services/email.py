"""Envío de correos: Resend (API por HTTPS) o SMTP, según las variables de entorno.

Si no hay proveedor configurado, los correos no se envían y solo se registra un
aviso: el resto de la aplicación sigue funcionando.
"""
import json
import logging
import smtplib
import ssl
import urllib.error
import urllib.request
from email.message import EmailMessage
from html import escape

from app.core.config import settings

logger = logging.getLogger("cartelera.email")


def send_email(to: str, subject: str, text: str, html: str | None = None) -> bool:
    if not settings.email_enabled:
        logger.warning("Correo no enviado a %s (%s): falta configurar el envío de correos.", to, subject)
        return False
    try:
        if settings.RESEND_API_KEY:
            _send_resend(to, subject, text, html)
        else:
            _send_smtp(to, subject, text, html)
        return True
    except Exception:  # el envío nunca debe tumbar la petición
        logger.exception("No se pudo enviar el correo a %s (%s)", to, subject)
        return False


def _send_resend(to: str, subject: str, text: str, html: str | None) -> None:
    body = {"from": settings.EMAIL_FROM, "to": [to], "subject": subject, "text": text}
    if html:
        body["html"] = html
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as res:
        if res.status >= 300:
            raise RuntimeError(f"Resend respondió {res.status}")


def _send_smtp(to: str, subject: str, text: str, html: str | None) -> None:
    msg = EmailMessage()
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    context = ssl.create_default_context()
    if settings.SMTP_USE_SSL:
        server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, context=context, timeout=15)
    else:
        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)
    with server:
        if not settings.SMTP_USE_SSL:
            server.starttls(context=context)
        if settings.SMTP_USER:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)


def frontend_link(path: str) -> str:
    return settings.FRONTEND_URL.rstrip("/") + path


def _layout(title: str, body_html: str, button_text: str | None = None, button_url: str | None = None) -> str:
    button = ""
    if button_text and button_url:
        button = (
            f'<p style="margin:28px 0"><a href="{escape(button_url)}" '
            'style="background:#0b263b;color:#ffffff;padding:12px 22px;border-radius:999px;'
            f'text-decoration:none;font-weight:600;display:inline-block">{escape(button_text)}</a></p>'
        )
    return (
        '<div style="background:#dceff7;padding:32px 16px;font-family:Arial,Helvetica,sans-serif">'
        '<div style="max-width:520px;margin:0 auto;background:#ffffff;border-radius:18px;padding:32px;color:#173447">'
        f'<p style="margin:0 0 6px;color:#087f91;font-weight:700">Cartelera · Admin Panel</p>'
        f'<h1 style="margin:0 0 16px;font-size:22px;color:#0b263b">{escape(title)}</h1>'
        f'{body_html}{button}'
        '<p style="margin:24px 0 0;font-size:12px;color:#557385">Si no esperabas este correo, puedes ignorarlo.</p>'
        '</div></div>'
    )


def send_password_reset(to: str, token: str) -> bool:
    url = frontend_link(f"/restablecer?token={token}")
    minutes = settings.PASSWORD_RESET_MINUTES
    text = (
        "Recibimos una solicitud para cambiar la contraseña de tu cuenta de Cartelera.\n\n"
        f"Abre este enlace para elegir una nueva (vale {minutes} minutos):\n{url}\n\n"
        "Si no fuiste tú, ignora este correo: tu contraseña no cambia."
    )
    html = _layout(
        "Restablecer tu contraseña",
        '<p style="margin:0;line-height:1.6">Recibimos una solicitud para cambiar la contraseña de tu cuenta. '
        f'El enlace vale {minutes} minutos.</p>',
        "Elegir nueva contraseña",
        url,
    )
    return send_email(to, "Restablecer tu contraseña de Cartelera", text, html)


def send_new_registration(to: str, new_user_email: str, new_user_name: str | None) -> bool:
    url = frontend_link("/admin/usuarios?estado=pendientes")
    who = f"{new_user_name} ({new_user_email})" if new_user_name else new_user_email
    text = f"{who} pidió acceso al panel de Cartelera.\n\nRevisa la solicitud: {url}"
    html = _layout(
        "Nueva solicitud de acceso",
        f'<p style="margin:0;line-height:1.6"><strong>{escape(who)}</strong> pidió acceso al panel. '
        'Apruébala y elige a qué secciones puede entrar.</p>',
        "Revisar solicitud",
        url,
    )
    return send_email(to, "Nueva solicitud de acceso a Cartelera", text, html)


def send_access_approved(to: str, modules: list[str]) -> bool:
    url = frontend_link("/login")
    listed = ", ".join(modules) if modules else "ninguna sección todavía"
    text = f"Tu acceso al panel de Cartelera fue aprobado.\n\nSecciones: {listed}\n\nEntra aquí: {url}"
    html = _layout(
        "Tu acceso fue aprobado",
        f'<p style="margin:0;line-height:1.6">Ya puedes entrar al panel. Secciones habilitadas: '
        f'<strong>{escape(listed)}</strong>.</p>',
        "Iniciar sesión",
        url,
    )
    return send_email(to, "Tu acceso a Cartelera fue aprobado", text, html)
