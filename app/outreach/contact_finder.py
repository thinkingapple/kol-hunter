import re
from app.scrapers.utils import extract_emails


def find_emails_from_kol(kol) -> list:
    """Extract all possible email addresses for a KOL from their profiles."""
    emails = set()

    # Direct email on KOL record
    if kol.email:
        emails.add(kol.email)

    # Scan all profile bios
    for profile in kol.profiles:
        if profile.bio_text:
            for email in extract_emails(profile.bio_text):
                emails.add(email)

    # Filter out generic / unlikely emails
    filtered = []
    for email in emails:
        lower = email.lower()
        # Skip generic addresses
        if any(x in lower for x in ["noreply", "no-reply", "support@", "info@youtube", "info@google"]):
            continue
        filtered.append(email)

    return filtered
