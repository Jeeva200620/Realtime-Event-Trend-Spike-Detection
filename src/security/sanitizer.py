import re
import html
import unicodedata

# Strict prompt-injection and jailbreak pattern detection
JAILBREAK_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?",
    r"you\s+are\s+now\s+(in\s+)?(developer\s+mode|unrestricted|god\s+mode|dan)",
    r"disregard\s+(all\s+)?(system\s+prompts?|instructions?)",
    r"system\s*:\s*",
    r"assistant\s*:\s*",
    r"human\s*:\s*",
    r"<\s*prompt\s*>",
    r"<\s*instructions?\s*>",
    r"```\s*(system|admin|eval)",
    r"output\s+only\s+(true|false|yes|no)",
    r"reveal\s+(your\s+)?(secret|token|api\s*key|system\s*prompt)",
]

COMPILED_JAILBREAKS = [re.compile(p, re.IGNORECASE) for p in JAILBREAK_PATTERNS]

class SecuritySanitizer:
    @staticmethod
    def clean_text(raw_text: str, max_chars: int = 250) -> str:
        """
        Sanitizes untrusted raw text from internet streams:
        1. Decodes HTML entities and strips tags.
        2. Strips markdown fences, delimiters, and terminal control chars.
        3. Removes known prompt-injection triggers.
        4. Truncates length to prevent buffer and token-flooding exploits.
        """
        if not raw_text or not isinstance(raw_text, str):
            return ""

        # 1. Unescape HTML and remove tags
        text = html.unescape(raw_text)
        text = re.sub(r"<[^>]+>", " ", text)

        # 2. Normalize unicode (NFKC) and strip non-printable/control chars
        text = unicodedata.normalize("NFKC", text)
        text = "".join(ch for ch in text if ch.isprintable() or ch in ("\n", "\t", " "))

        # 3. Strip dangerous markdown code fences and delimiter hijacking
        text = re.sub(r"[`~]{3,}", " ", text)
        text = re.sub(r"[-=]{3,}", " ", text)

        # 4. Neutralize jailbreak/injection phrases
        for pattern in COMPILED_JAILBREAKS:
            text = pattern.sub("[REDACTED_ATTEMPT]", text)

        # 5. Clean whitespace & collapse multiple newlines
        text = re.sub(r"\s+", " ", text).strip()

        # 6. Hard truncation
        if len(text) > max_chars:
            text = text[:max_chars].rstrip() + "..."

        return text

    @staticmethod
    def wrap_untrusted_context(sanitized_text: str) -> str:
        """
        Encapsulates untrusted event text inside secure XML boundaries
        for safe LLM parsing.
        """
        return f"<untrusted_event_text>\n{sanitized_text}\n</untrusted_event_text>"
