"""Сповіщення: email (SMTP), Slack (incoming webhook), Telegram (bot API).

Усі відправлення best-effort у фонових потоках — збій пошти не має ламати
запит. Якщо канал не сконфігуровано, виклик мовчки пропускається.
"""

import logging
import smtplib
import threading
from datetime import date
from email.mime.text import MIMEText

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.models import (
    ActionStatus,
    Control,
    Finding,
    Policy,
    PolicyStatus,
    PolicyVersion,
    Risk,
    RiskStatus,
    TreatmentAction,
    User,
)

logger = logging.getLogger(__name__)


def email_configured() -> bool:
    return bool(get_settings().smtp_host)


def _send_email_sync(to: str, subject: str, body: str) -> None:
    settings = get_settings()
    message = MIMEText(body, "plain", "utf-8")
    message["Subject"] = subject
    message["From"] = settings.smtp_from
    message["To"] = to
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            if settings.smtp_starttls:
                server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(message)
    except Exception:
        logger.exception("Не вдалося надіслати email до %s", to)


def send_email(to: str, subject: str, body: str) -> None:
    if not email_configured():
        return
    threading.Thread(target=_send_email_sync, args=(to, subject, body), daemon=True).start()


def _post_json(url: str, payload: dict) -> None:
    try:
        httpx.post(url, json=payload, timeout=10)
    except Exception:
        logger.exception("Не вдалося надіслати сповіщення на %s", url.split("?")[0][:60])


def send_channel(text: str) -> None:
    """Надсилає повідомлення в налаштовані месенджери (Slack та/або Telegram)."""
    settings = get_settings()
    if settings.slack_webhook_url:
        threading.Thread(
            target=_post_json, args=(settings.slack_webhook_url, {"text": text}), daemon=True
        ).start()
    if settings.telegram_bot_token and settings.telegram_chat_id:
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
        threading.Thread(
            target=_post_json,
            args=(url, {"chat_id": settings.telegram_chat_id, "text": text}),
            daemon=True,
        ).start()


def notify_user(user: User | None, subject: str, body: str) -> None:
    if user is None or not user.is_active:
        return
    base_url = get_settings().base_url
    if base_url:
        body = f"{body}\n\n{base_url}"
    send_email(user.email, subject, body)


# --- Щоденний дайджест прострочень ---

_OPEN_RISK_STATUSES = [s.value for s in RiskStatus if s != RiskStatus.CLOSED]
_OPEN_ACTION_STATUSES = [ActionStatus.OPEN.value, ActionStatus.IN_PROGRESS.value]


def build_digest(db: Session) -> tuple[dict[str, list[str]], list[str]]:
    """Повертає (рядки за email відповідального, підсумкові рядки для каналу)."""
    today = date.today()
    per_user: dict[str, list[str]] = {}
    summary: list[str] = []

    def add(user: User | None, line: str) -> None:
        if user is not None and user.is_active:
            per_user.setdefault(user.email, []).append(line)

    overdue_risks = db.scalars(
        select(Risk)
        .where(Risk.next_review_date < today, Risk.status.in_(_OPEN_RISK_STATUSES))
        .options(selectinload(Risk.owner))
    ).all()
    for risk in overdue_risks:
        add(risk.owner, f"Прострочений перегляд ризику {risk.code} — {risk.title} "
                        f"(до {risk.next_review_date:%d.%m.%Y})")

    overdue_controls = db.scalars(
        select(Control)
        .where(Control.next_review_date < today)
        .options(selectinload(Control.owner))
    ).all()
    for control in overdue_controls:
        add(control.owner, f"Прострочена перевірка контролю {control.code} — {control.name} "
                           f"(до {control.next_review_date:%d.%m.%Y})")

    overdue_actions = db.scalars(
        select(TreatmentAction)
        .where(
            TreatmentAction.deadline < today,
            TreatmentAction.status.in_(_OPEN_ACTION_STATUSES),
        )
        .options(selectinload(TreatmentAction.assignee), selectinload(TreatmentAction.risk))
    ).all()
    for action in overdue_actions:
        add(action.assignee, f"Прострочена дія «{action.title}» за ризиком "
                             f"{action.risk.code} (до {action.deadline:%d.%m.%Y})")

    overdue_findings = db.scalars(
        select(Finding)
        .where(Finding.deadline < today, Finding.action_status.in_(_OPEN_ACTION_STATUSES))
        .options(selectinload(Finding.responsible))
    ).all()
    for finding in overdue_findings:
        add(finding.responsible, f"Прострочена коригувальна дія за знахідкою {finding.code} — "
                                 f"{finding.title} (до {finding.deadline:%d.%m.%Y})")

    overdue_policies = db.scalars(
        select(Policy)
        .where(Policy.next_review_date < today, Policy.status == PolicyStatus.ACTIVE.value)
        .options(selectinload(Policy.owner))
    ).all()
    for policy in overdue_policies:
        add(policy.owner, f"Прострочений перегляд політики {policy.code} — {policy.title} "
                          f"(до {policy.next_review_date:%d.%m.%Y})")

    pending_acks = db.scalars(
        select(PolicyVersion)
        .options(selectinload(PolicyVersion.acks), selectinload(PolicyVersion.policy))
    ).all()
    pending_ack_count = 0
    for version in pending_acks:
        if version.policy.status != PolicyStatus.ACTIVE.value:
            continue
        if version is not version.policy.current_version:
            continue
        for ack in version.acks:
            if ack.acknowledged_at is None:
                pending_ack_count += 1
                add(ack.user, f"Очікує вашого ознайомлення: політика "
                              f"{version.policy.code} — {version.policy.title}")

    counts = {
        "ризики (перегляд)": len(overdue_risks),
        "контролі (перевірка)": len(overdue_controls),
        "дії з обробки": len(overdue_actions),
        "коригувальні дії": len(overdue_findings),
        "політики (перегляд)": len(overdue_policies),
        "непідтверджені ознайомлення": pending_ack_count,
    }
    if any(counts.values()):
        summary.append("GRC: прострочення на " + today.strftime("%d.%m.%Y"))
        for label, count in counts.items():
            if count:
                summary.append(f"• {label}: {count}")
    return per_user, summary


def send_daily_digest() -> None:
    from app.database import SessionLocal

    with SessionLocal() as db:
        per_user, summary = build_digest(db)
    for email, lines in per_user.items():
        send_email(
            email,
            "GRC: ваші прострочені задачі",
            "Доброго дня!\n\nПотребують вашої уваги:\n\n- " + "\n- ".join(lines),
        )
    if summary:
        send_channel("\n".join(summary))
    logger.info("Дайджест: %d адресатів, канал: %s", len(per_user), bool(summary))
