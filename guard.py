"""Guard layer: blocks prompt injection / jailbreaks and redacts personal data."""
import re
import time

from transformers import pipeline

MODEL_DIR = "model"
THRESHOLD = 0.5  # attack probability at or above this blocks the prompt
BLOCK_MESSAGE = "I'm sorry, but I cannot help with that request. [blocked by LLM firewall]"

# Order matters: longer/stricter patterns run first so e.g. an Aadhaar number is not read as a phone.
# shortcut: regex only finds structured PII (no names/addresses); swap in an NER model (e.g. Presidio) if you need those.
PII_PATTERNS = {
    "API_KEY": r"\b(?:sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36})\b",
    "EMAIL": r"[\w.+-]+@[\w-]+\.[\w.-]+",
    "CARD": r"\b\d(?:[ -]?\d){12,18}\b",
    "AADHAAR": r"\b[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}\b",
    "PAN": r"\b[A-Z]{5}\d{4}[A-Z]\b",
    "PHONE": r"(?<!\d)(?:\+\d{1,3}[ -]?)?(?:\d{5}[ -]?\d{5}|\(?\d{3}\)?[ -]?\d{3}[ -]?\d{4})(?!\d)",
}


def luhn_ok(digits: str) -> bool:
    total = 0
    for i, d in enumerate(int(c) for c in reversed(digits)):
        if i % 2:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


def redact(text: str) -> tuple[str, list[str]]:
    """Replace personal data with [TYPE] tags; return the clean text and the types found."""
    found = []
    for kind, pattern in PII_PATTERNS.items():
        def repl(m, kind=kind):
            if kind == "CARD" and not luhn_ok(re.sub(r"\D", "", m.group())):
                return m.group()  # long number that is not a valid card
            found.append(kind)
            return f"[{kind}]"
        text = re.sub(pattern, repl, text)
    return text, found


class Guard:
    def __init__(self, model_dir: str = MODEL_DIR, threshold: float = THRESHOLD):
        # shortcut: only the first 256 tokens are scored; slide a window over long prompts if attacks hide at the end.
        self.clf = pipeline("text-classification", model=model_dir, truncation=True, max_length=256)
        self.threshold = threshold

    def attack_score(self, text: str) -> float:
        scores = self.clf(text, top_k=None)
        return next(s["score"] for s in scores if s["label"] == "ATTACK")

    def check_input(self, prompt: str) -> dict:
        start = time.perf_counter()
        score = self.attack_score(prompt)
        clean, pii = redact(prompt)
        return {
            "blocked": score >= self.threshold,
            "attack_score": round(score, 4),
            "clean_prompt": clean,
            "pii_in": pii,
            "guard_ms": round((time.perf_counter() - start) * 1000, 1),
        }

    def check_output(self, text: str) -> tuple[str, list[str]]:
        return redact(text)
