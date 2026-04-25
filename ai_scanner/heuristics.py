"""Post-AI heuristic safety net.

When the AI returns 'safe' on content that has unmistakable phishing
fingerprints (password input + sensitive form fields, brand keywords on a
domain that doesn't own them, obfuscated scripts), force the verdict up
to 'suspicious' or 'scam'. Also feed the same hints back into the AI
prompt as a CONCRETE_TOKENS section so the model can't credibly miss
them.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class HeuristicReport:
    has_password_field: bool
    has_card_field: bool
    has_otp_field: bool
    has_seed_phrase_ask: bool
    obfuscated_script_count: int
    cred_brand_terms: list[str]    # paypal/maybank/etc. mentioned in copy
    suspicious_keywords: list[str]
    free_tld: bool


# Risk-amplifying TLDs where legit brands rarely live.
SUSPICIOUS_TLDS = {
    "tk", "ml", "ga", "cf", "gq",     # Freenom (most defunct but still seen)
    "xyz", "top", "click", "loan", "work", "rest", "live",
    "support", "info-secure", "id",
}

BRAND_KEYWORDS = (
    "paypal", "facebook", "instagram", "whatsapp", "tiktok", "linkedin",
    "google", "gmail", "apple", "icloud", "microsoft", "outlook", "office365",
    "amazon", "netflix", "spotify", "discord",
    "maybank", "cimb", "publicbank", "rhb", "ambank", "hongleong", "bsn",
    "bank", "bnm", "dudm",
    "binance", "coinbase", "metamask", "trustwallet", "ledger", "trezor",
    "shopee", "lazada", "grab", "foodpanda",
)

URGENCY_PHRASES = (
    "your account will be locked", "verify within", "limited time",
    "act now", "last chance", "expire", "suspend", "unusual activity",
    "secure your account", "claim now", "congratulations you have won",
    "you are eligible",
)

OBFUSCATED_SCRIPT_RE = re.compile(
    r"(eval\(|atob\(|fromCharCode|unescape\(|String\.fromCharCode|"
    r"document\.write\(|\\x[0-9a-fA-F]{2}|\\u[0-9a-fA-F]{4})"
)

PASSWORD_FIELD_RE = re.compile(
    r"<input[^>]*type=['\"]?password['\"]?", re.IGNORECASE
)

CARD_FIELD_RE = re.compile(
    r"(card[_-]?number|cardnumber|cc[_-]?num|cvv|cvc|"
    r"name=['\"]?(card|cvv|cvc|expiry|exp_)['\"]?)",
    re.IGNORECASE,
)

OTP_FIELD_RE = re.compile(
    r"(name=['\"]?(otp|tac|2fa|mfa|verification[_-]?code|sms[_-]?code)['\"]?|"
    r"placeholder=['\"][^'\"]*?(otp|verification code|6.?digit)[^'\"]*?['\"])",
    re.IGNORECASE,
)

SEED_PHRASE_RE = re.compile(
    r"(seed[_ -]?phrase|recovery[_ -]?phrase|12[_ -]?word|24[_ -]?word|"
    r"mnemonic[_ -]?phrase|secret[_ -]?recovery)",
    re.IGNORECASE,
)


def analyze(html: str, domain: str) -> HeuristicReport:
    lowered = html.lower()
    label = domain.lower().split(".")[-2] if "." in domain else domain.lower()

    cred_brand_terms = [
        b for b in BRAND_KEYWORDS
        if b in lowered and b != label  # mentioned but not the actual brand
    ]
    sus_keywords = [p for p in URGENCY_PHRASES if p in lowered]

    tld = domain.rsplit(".", 1)[-1].lower() if "." in domain else ""

    return HeuristicReport(
        has_password_field=bool(PASSWORD_FIELD_RE.search(html)),
        has_card_field=bool(CARD_FIELD_RE.search(html)),
        has_otp_field=bool(OTP_FIELD_RE.search(html)),
        has_seed_phrase_ask=bool(SEED_PHRASE_RE.search(html)),
        obfuscated_script_count=len(OBFUSCATED_SCRIPT_RE.findall(html)),
        cred_brand_terms=cred_brand_terms[:8],
        suspicious_keywords=sus_keywords[:6],
        free_tld=tld in SUSPICIOUS_TLDS,
    )


def render_for_prompt(report: HeuristicReport) -> str:
    """Compact human-readable summary the prompt can read alongside HTML.
    Helps the AI focus on real signals rather than skim a long HTML blob."""
    lines: list[str] = []
    if report.has_password_field:
        lines.append("- HTML contains <input type=password>")
    if report.has_card_field:
        lines.append("- HTML contains a credit-card field (card number / CVV / expiry)")
    if report.has_otp_field:
        lines.append("- HTML contains an OTP / 2FA / TAC field")
    if report.has_seed_phrase_ask:
        lines.append("- Page asks for a wallet seed / recovery phrase")
    if report.obfuscated_script_count >= 3:
        lines.append(
            f"- {report.obfuscated_script_count} obfuscated-JS markers "
            f"(eval/atob/fromCharCode/escape sequences)"
        )
    if report.cred_brand_terms:
        lines.append(
            "- Brand names mentioned in copy that the domain does NOT own: "
            + ", ".join(report.cred_brand_terms)
        )
    if report.suspicious_keywords:
        lines.append(
            "- Urgency / scam phrases found: "
            + "; ".join(f'"{p}"' for p in report.suspicious_keywords)
        )
    if report.free_tld:
        lines.append("- Domain uses a high-abuse TLD (free / low-cost)")
    if not lines:
        return "- No high-risk tokens detected by static scan."
    return "\n".join(lines)


def severity_floor(report: HeuristicReport, domain: str) -> tuple[str, list[str]]:
    """Compute a *minimum* verdict + reasons that the AI cannot weaken below.

    Conservative: avoid raising for legitimate sites that incidentally have
    a password field (e.g. their actual login). The signal must combine
    with at least one extra red flag (brand mention not their own, free
    TLD, obfuscation) before we override 'safe'.
    """
    extra_flags = (
        bool(report.cred_brand_terms)
        or report.free_tld
        or report.obfuscated_script_count >= 3
        or report.has_otp_field
        or report.has_card_field
        or report.has_seed_phrase_ask
    )
    reasons: list[str] = []

    if report.has_seed_phrase_ask:
        reasons.append("Page requests a wallet seed / recovery phrase")
        return ("scam", reasons)

    if report.has_card_field and (report.cred_brand_terms or report.free_tld):
        reasons.append(
            "Credit-card form on a domain that doesn't own the brand it mentions"
            if report.cred_brand_terms
            else "Credit-card form on a high-abuse TLD"
        )
        return ("scam", reasons)

    if report.has_password_field and extra_flags:
        if report.cred_brand_terms:
            reasons.append(
                "Password field plus brand impersonation: domain mentions "
                + ", ".join(report.cred_brand_terms)
                + " in copy without owning the trademark"
            )
        elif report.free_tld:
            reasons.append("Password field on a high-abuse TLD")
        elif report.obfuscated_script_count >= 3:
            reasons.append(
                "Password field plus heavy script obfuscation "
                f"({report.obfuscated_script_count} markers)"
            )
        elif report.has_otp_field:
            reasons.append("Password field plus OTP / 2FA capture")
        return ("suspicious", reasons)

    if report.obfuscated_script_count >= 5:
        reasons.append(
            f"Heavy script obfuscation ({report.obfuscated_script_count} markers)"
        )
        return ("suspicious", reasons)

    if report.cred_brand_terms and report.free_tld:
        reasons.append(
            f"Free TLD '.{domain.rsplit('.', 1)[-1]}' plus brand mentions: "
            + ", ".join(report.cred_brand_terms)
        )
        return ("suspicious", reasons)

    return ("safe", reasons)
