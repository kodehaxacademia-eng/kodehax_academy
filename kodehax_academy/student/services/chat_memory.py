from __future__ import annotations

from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Prefetch
from django.utils import timezone

from adminpanel.models import PlatformSettings
from student.models import ChatMessage, ChatSession


def get_memory_settings():
    settings_obj = PlatformSettings.load()
    duration_minutes = max(1, int(settings_obj.chat_memory_duration or 30))
    max_messages = max(1, int(settings_obj.max_messages_per_session or 12))
    return {
        "enabled": bool(settings_obj.enable_chat_memory),
        "duration_minutes": duration_minutes,
        "max_messages_per_session": max_messages,
    }


def build_expiry_from_now(duration_minutes: int):
    return timezone.now() + timedelta(minutes=duration_minutes)


def generate_session_title(message: str):
    words = [token for token in (message or "").strip().split() if token]
    if not words:
        return ""
    return " ".join(words[:7])[:255]


def create_chat_session(user, first_message: str = ""):
    memory = get_memory_settings()
    return ChatSession.objects.create(
        user=user,
        title=generate_session_title(first_message),
        expires_at=build_expiry_from_now(memory["duration_minutes"]),
    )


def get_user_session_or_404(user, session_id):
    return ChatSession.objects.get(user=user, pk=session_id)


def get_valid_messages(session: ChatSession):
    memory = get_memory_settings()
    if not memory["enabled"]:
        return ChatMessage.objects.none()
    cutoff = timezone.now() - timedelta(minutes=memory["duration_minutes"])
    return session.messages.filter(created_at__gte=cutoff).order_by("created_at", "id")


def compact_session_summary(session: ChatSession, messages):
    preview_parts = []
    for message in list(messages)[-4:]:
        prefix = "U" if message.role == ChatMessage.ROLE_USER else "A"
        preview_parts.append(f"{prefix}: {message.content[:120]}")
    return " | ".join(preview_parts)[:500]


def build_context_payload(session: ChatSession, user_profile: dict):
    memory = get_memory_settings()
    valid_messages_qs = get_valid_messages(session)
    recent_messages = list(valid_messages_qs.order_by("-created_at", "-id")[: memory["max_messages_per_session"]])
    recent_messages.reverse()
    return {
        "session_summary": compact_session_summary(session, recent_messages),
        "recent_messages": [{"role": item.role, "content": item.content} for item in recent_messages],
        "user_profile": user_profile,
        "memory": memory,
    }


def append_message(session: ChatSession, role: str, content: str):
    message = ChatMessage.objects.create(session=session, role=role, content=content)
    memory = get_memory_settings()
    session.updated_at = timezone.now()
    if memory["enabled"]:
        session.expires_at = build_expiry_from_now(memory["duration_minutes"])
    session.save(update_fields=["updated_at", "expires_at"])
    return message


def list_active_sessions(user, page_number=1, per_page=20):
    qs = (
        ChatSession.objects.filter(user=user, is_active=True, expires_at__gt=timezone.now())
        .prefetch_related(
            Prefetch(
                "messages",
                queryset=ChatMessage.objects.order_by("-created_at", "-id"),
                to_attr="prefetched_messages",
            )
        )
        .order_by("-updated_at")
    )
    paginator = Paginator(qs, per_page)
    return paginator.get_page(page_number)


def cleanup_expired_sessions(delete=False):
    expired = ChatSession.objects.filter(expires_at__lte=timezone.now())
    if delete:
        count = expired.count()
        expired.delete()
        return count
    return expired.update(is_active=False)
