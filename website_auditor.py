"""
Website Opportunity Auditor - Phase 1
--------------------------------------
Audits a business website and scores it out of 100.
Designed for South African service businesses (plumbers, electricians, etc.)

Usage:
    python website_auditor.py https://example.co.za
    python website_auditor.py https://example.co.za --json
"""

import sys
import re
import time
import json
import argparse
from datetime import datetime
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}
TIMEOUT = 15  # seconds

FREE_PLATFORMS = [
    "wixsite.com", "wix.com",
    "weebly.com",
    "wordpress.com",
    "blogspot.com",
    "godaddysites.com",
    "squarespace.com",  # not free but same signal
    "site123.me",
    "webnode.com",
]

CTA_KEYWORDS = [
    "get a quote", "get quote", "free quote",
    "book now", "book a", "schedule",
    "contact us", "call us", "call now",
    "whatsapp us", "send message",
    "request a quote", "get started",
    "enquire now", "enquire",
]

TESTIMONIAL_KEYWORDS = [
    "testimonial", "review", "what our clients",
    "what customers say", "client says", "happy customer",
    "5 star", "five star", "rated",
]

PORTFOLIO_KEYWORDS = [
    "portfolio", "gallery", "our work",
    "projects", "before and after", "before & after",
    "case study", "examples",
]

WHATSAPP_PATTERNS = [
    r"wa\.me",
    r"whatsapp",
    r"api\.whatsapp\.com",
]

SOCIAL_PATTERNS = [
    r"facebook\.com", r"instagram\.com",
    r"twitter\.com", r"x\.com",
    r"linkedin\.com", r"youtube\.com",
    r"tiktok\.com",
]

# ─────────────────────────────────────────────
# SCORING WEIGHTS  (penalties deducted from 100)
# ─────────────────────────────────────────────

WEIGHTS = {
    # Contact — most important for SA trades
    "no_whatsapp":          15,
    "gmail_email":          8,
    "no_contact_form":      5,
    "no_click_to_call":     5,

    # Domain / Platform
    "free_platform":        10,
    "no_https":             10,

    # Marketing / Conversion
    "no_cta":               10,
    "no_testimonials":      5,
    "no_portfolio":         5,

    # SEO
    "no_title":             5,
    "no_description":       3,
    "no_h1":                5,

    # Trust
    "old_copyright":        3,
    "no_privacy_policy":    3,

    # Technical
    "no_mobile_viewport":   8,
    "no_favicon":           2,
    "no_social_links":      3,
}

# ─────────────────────────────────────────────
# FETCHER
# ─────────────────────────────────────────────

def fetch_page(url: str):
    """Fetch a URL and return (response, soup, load_time_ms, error)."""
    try:
        start = time.time()
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        load_time = round((time.time() - start) * 1000)
        soup = BeautifulSoup(resp.text, "lxml")
        return resp, soup, load_time, None
    except requests.exceptions.SSLError:
        return None, None, None, "SSL_ERROR"
    except requests.exceptions.ConnectionError:
        return None, None, None, "CONNECTION_ERROR"
    except requests.exceptions.Timeout:
        return None, None, None, "TIMEOUT"
    except Exception as e:
        return None, None, None, str(e)


# ─────────────────────────────────────────────
# INDIVIDUAL CHECKS
# ─────────────────────────────────────────────

def check_domain(url: str) -> dict:
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    is_free_platform = any(fp in domain for fp in FREE_PLATFORMS)
    is_co_za = domain.endswith(".co.za")
    is_https = parsed.scheme == "https"

    return {
        "domain": domain,
        "is_co_za": is_co_za,
        "is_https": is_https,
        "is_free_platform": is_free_platform,
        "platform_name": next((fp for fp in FREE_PLATFORMS if fp in domain), None),
    }


def check_contact(soup: BeautifulSoup, html: str) -> dict:
    html_lower = html.lower()

    # WhatsApp
    has_whatsapp = any(re.search(p, html_lower) for p in WHATSAPP_PATTERNS)

    # Email addresses
    emails = re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", html)
    has_gmail = any("@gmail.com" in e.lower() for e in emails)
    has_company_email = any(
        "@gmail.com" not in e.lower() and
        "@yahoo.com" not in e.lower() and
        "@hotmail.com" not in e.lower()
        for e in emails
    )

    # Contact form
    forms = soup.find_all("form")
    has_contact_form = len(forms) > 0

    # Click to call
    tel_links = soup.find_all("a", href=re.compile(r"^tel:"))
    has_click_to_call = len(tel_links) > 0

    return {
        "has_whatsapp": has_whatsapp,
        "emails": list(set(emails))[:5],
        "has_gmail": has_gmail,
        "has_company_email": has_company_email,
        "has_contact_form": has_contact_form,
        "has_click_to_call": has_click_to_call,
    }


def check_technical(soup: BeautifulSoup, load_time_ms: int) -> dict:
    # Mobile viewport
    viewport = soup.find("meta", attrs={"name": "viewport"})
    has_viewport = viewport is not None

    # Favicon
    favicon = soup.find("link", rel=lambda r: r and "icon" in " ".join(r).lower())
    has_favicon = favicon is not None

    # Slow load (over 4 seconds is noticeable)
    is_slow = load_time_ms > 4000

    return {
        "has_mobile_viewport": has_viewport,
        "has_favicon": has_favicon,
        "load_time_ms": load_time_ms,
        "is_slow": is_slow,
    }


def check_seo(soup: BeautifulSoup) -> dict:
    # Title
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else None

    # Meta description
    desc_tag = soup.find("meta", attrs={"name": "description"})
    description = desc_tag.get("content", "").strip() if desc_tag else None

    # H1
    h1_tags = soup.find_all("h1")
    h1_text = h1_tags[0].get_text(strip=True) if h1_tags else None

    # Schema markup
    schema = soup.find("script", attrs={"type": "application/ld+json"})
    has_schema = schema is not None

    return {
        "title": title,
        "has_title": bool(title),
        "description": description,
        "has_description": bool(description),
        "h1": h1_text,
        "has_h1": bool(h1_text),
        "has_schema": has_schema,
    }


def check_marketing(soup: BeautifulSoup, html: str) -> dict:
    html_lower = html.lower()

    has_cta = any(kw in html_lower for kw in CTA_KEYWORDS)
    has_testimonials = any(kw in html_lower for kw in TESTIMONIAL_KEYWORDS)
    has_portfolio = any(kw in html_lower for kw in PORTFOLIO_KEYWORDS)
    has_google_maps = "maps.google" in html_lower or "google.com/maps" in html_lower or "maps.googleapis" in html_lower

    # Social links
    links = soup.find_all("a", href=True)
    social_links = [
        a["href"] for a in links
        if any(re.search(p, a["href"].lower()) for p in SOCIAL_PATTERNS)
    ]

    return {
        "has_cta": has_cta,
        "has_testimonials": has_testimonials,
        "has_portfolio": has_portfolio,
        "has_google_maps": has_google_maps,
        "social_links": list(set(social_links))[:5],
        "has_social_links": len(social_links) > 0,
    }


def check_trust(soup: BeautifulSoup, html: str) -> dict:
    html_lower = html.lower()

    has_privacy_policy = "privacy policy" in html_lower or "privacy-policy" in html_lower
    has_terms = "terms" in html_lower and ("conditions" in html_lower or "service" in html_lower)

    # Copyright year
    copyright_match = re.search(r"©\s*(\d{4})|copyright\s*[©]?\s*(\d{4})", html_lower)
    copyright_year = None
    old_copyright = False
    if copyright_match:
        year_str = copyright_match.group(1) or copyright_match.group(2)
        if year_str:
            copyright_year = int(year_str)
            old_copyright = copyright_year < (datetime.now().year - 2)

    return {
        "has_privacy_policy": has_privacy_policy,
        "has_terms": has_terms,
        "copyright_year": copyright_year,
        "old_copyright": old_copyright,
    }


# ─────────────────────────────────────────────
# SCORER
# ─────────────────────────────────────────────

def calculate_score(domain_data, contact_data, technical_data, seo_data, marketing_data, trust_data):
    score = 100
    issues = []
    positives = []

    def deduct(key, message):
        nonlocal score
        score -= WEIGHTS[key]
        issues.append(f"❌ {message}  (-{WEIGHTS[key]} pts)")

    def positive(message):
        positives.append(f"✅ {message}")

    # Domain
    if domain_data["is_free_platform"]:
        deduct("free_platform", f"Free platform domain ({domain_data['platform_name']})")
    else:
        positive("Custom domain")

    if not domain_data["is_https"]:
        deduct("no_https", "No HTTPS (insecure site)")
    else:
        positive("HTTPS secure")

    # Contact
    if not contact_data["has_whatsapp"]:
        deduct("no_whatsapp", "No WhatsApp button or link")
    else:
        positive("WhatsApp contact available")

    if contact_data["has_gmail"]:
        deduct("gmail_email", "Uses Gmail instead of company email")
    elif contact_data["has_company_email"]:
        positive("Company email address")

    if not contact_data["has_contact_form"]:
        deduct("no_contact_form", "No contact form")
    else:
        positive("Contact form present")

    if not contact_data["has_click_to_call"]:
        deduct("no_click_to_call", "No click-to-call phone link")
    else:
        positive("Click-to-call enabled")

    # Technical
    if not technical_data["has_mobile_viewport"]:
        deduct("no_mobile_viewport", "Not mobile-friendly (no viewport meta)")
    else:
        positive("Mobile-friendly")

    if not technical_data["has_favicon"]:
        deduct("no_favicon", "Missing favicon")
    else:
        positive("Favicon present")

    # Marketing
    if not marketing_data["has_cta"]:
        deduct("no_cta", "No clear call-to-action button")
    else:
        positive("Has call-to-action")

    if not marketing_data["has_testimonials"]:
        deduct("no_testimonials", "No testimonials or reviews")
    else:
        positive("Has testimonials/reviews")

    if not marketing_data["has_portfolio"]:
        deduct("no_portfolio", "No portfolio or gallery")
    else:
        positive("Has portfolio/gallery")

    if not marketing_data["has_social_links"]:
        deduct("no_social_links", "No social media links")
    else:
        positive("Social media links present")

    # SEO
    if not seo_data["has_title"]:
        deduct("no_title", "Missing page title (SEO)")
    else:
        positive("Page title set")

    if not seo_data["has_description"]:
        deduct("no_description", "Missing meta description (SEO)")
    else:
        positive("Meta description set")

    if not seo_data["has_h1"]:
        deduct("no_h1", "Missing H1 heading")
    else:
        positive("H1 heading present")

    # Trust
    if trust_data["old_copyright"]:
        deduct("old_copyright", f"Outdated copyright year ({trust_data['copyright_year']})")
    elif trust_data["copyright_year"]:
        positive(f"Copyright up to date ({trust_data['copyright_year']})")

    if not trust_data["has_privacy_policy"]:
        deduct("no_privacy_policy", "No privacy policy (POPIA concern)")
    else:
        positive("Privacy policy present")

    score = max(0, score)
    return score, issues, positives


def opportunity_rating(score: int) -> tuple:
    if score <= 35:
        return "🔥 HOT", "High opportunity — major improvements needed"
    elif score <= 55:
        return "⭐⭐⭐⭐", "Strong opportunity — several quick wins available"
    elif score <= 70:
        return "⭐⭐⭐", "Medium opportunity — a few improvements possible"
    elif score <= 85:
        return "⭐⭐", "Low opportunity — site is reasonably good"
    else:
        return "⭐", "Minimal opportunity — site is well optimised"


# ─────────────────────────────────────────────
# MAIN AUDIT
# ─────────────────────────────────────────────

def audit(url: str, business_name: str = None) -> dict:
    print(f"\n🔍 Auditing: {url}")
    print("─" * 50)

    # Ensure URL has scheme
    if not url.startswith("http"):
        url = "https://" + url

    # Fetch
    resp, soup, load_time, error = fetch_page(url)

    if error or soup is None:
        # Try http fallback
        if error == "SSL_ERROR":
            print("⚠️  HTTPS failed, trying HTTP...")
            url = url.replace("https://", "http://")
            resp, soup, load_time, error = fetch_page(url)

    if error or soup is None:
        return {
            "url": url,
            "error": error,
            "score": 0,
            "issues": [f"❌ Could not fetch website: {error}"],
            "positives": [],
        }

    html = resp.text

    # Run checks
    domain_data    = check_domain(url)
    contact_data   = check_contact(soup, html)
    technical_data = check_technical(soup, load_time)
    seo_data       = check_seo(soup)
    marketing_data = check_marketing(soup, html)
    trust_data     = check_trust(soup, html)

    # Score
    score, issues, positives = calculate_score(
        domain_data, contact_data, technical_data,
        seo_data, marketing_data, trust_data
    )

    rating_label, rating_desc = opportunity_rating(score)

    return {
        "url": url,
        "business_name": business_name or domain_data["domain"],
        "score": score,
        "rating": rating_label,
        "rating_desc": rating_desc,
        "issues": issues,
        "positives": positives,
        "load_time_ms": load_time,
        "details": {
            "domain": domain_data,
            "contact": contact_data,
            "technical": technical_data,
            "seo": seo_data,
            "marketing": marketing_data,
            "trust": trust_data,
        }
    }


# ─────────────────────────────────────────────
# OUTPUT FORMATTER
# ─────────────────────────────────────────────

def print_report(result: dict):
    if "error" in result and result["score"] == 0:
        print(f"\n💥 Audit failed: {result['error']}")
        return

    score = result["score"]
    bar_filled = int(score / 5)
    bar = "█" * bar_filled + "░" * (20 - bar_filled)

    print(f"""
╔══════════════════════════════════════════════╗
║         🌐 WEBSITE OPPORTUNITY AUDIT         ║
╚══════════════════════════════════════════════╝

  Business : {result['business_name']}
  URL      : {result['url']}
  Audited  : {datetime.now().strftime('%d %b %Y %H:%M')}
  Load time: {result['load_time_ms']}ms

  SCORE: {score}/100
  [{bar}]

  Opportunity: {result['rating']}
  {result['rating_desc']}
""")

    if result["issues"]:
        print("  ── PROBLEMS FOUND ──────────────────────────")
        for issue in result["issues"]:
            print(f"  {issue}")

    if result["positives"]:
        print("\n  ── WHAT'S WORKING ──────────────────────────")
        for pos in result["positives"]:
            print(f"  {pos}")

    print("\n" + "─" * 50)


def telegram_format(result: dict) -> str:
    """Format result as a Telegram message (plain text)."""
    if "error" in result and result.get("score") == 0:
        return f"🚨 Audit Failed\n\n🌐 {result.get('url', 'Unknown URL')}\n❌ Error: {result.get('error')}"

    score = result["score"]
    issues_text = "\n".join(result["issues"][:6])
    rating = result["rating"]

    return f"""🚨 New Opportunity Found

*{result['business_name']}*
🌐 {result['url']}

📊 Website Score: *{score}/100*
{rating}

🔴 Problems:
{issues_text}

💡 {result['rating_desc']}
⏱ Load time: {result['load_time_ms']}ms
"""


# ─────────────────────────────────────────────
# CLI ENTRY POINT
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Website Opportunity Auditor")
    parser.add_argument("url", help="Website URL to audit")
    parser.add_argument("--name", help="Business name (optional)", default=None)
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument("--telegram", action="store_true", help="Output Telegram-formatted message")
    args = parser.parse_args()

    result = audit(args.url, business_name=args.name)

    if args.json:
        print(json.dumps(result, indent=2))
    elif args.telegram:
        print(telegram_format(result))
    else:
        print_report(result)


if __name__ == "__main__":
    main()