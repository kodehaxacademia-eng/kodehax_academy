import re

# Keep formatting helpers in one place so multiple chat endpoints can reuse them.
RESPONSE_STYLE_INSTRUCTION = (
    "Formatting requirements:\n"
    "- Start with a direct answer in 1-2 sentences.\n"
    "- Use short sections with clear headings when helpful.\n"
    "- Use bullet points for steps and key ideas.\n"
    "- Keep paragraphs short (max 3 lines).\n"
    "- Use code fences for code examples.\n"
    "- Avoid filler language.\n"
)


def format_ai_reply(reply: str) -> str:
    if not isinstance(reply, str):
        return ""

    normalized = reply.replace("\r\n", "\n").replace("\r", "\n")
    normalized = "\n".join(line.rstrip() for line in normalized.split("\n"))
    normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
    return normalized
