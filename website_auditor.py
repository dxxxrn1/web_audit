import re
import time
from datetime import datetime
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


HEADERS = {"User-Agent": "Mozilla/5.0"}
TIMEOUT = 15


FREE_PLATFORMS = [
    "wixsite.com", "wix.com", "weebly.com",
    "wordpress.com", "blogspot.com",
    "godaddysites.com", "squarespace.com",
]


# ─────────────────────────────────────────────
# FETCH PAGE
# ─────────────────────────────────────────────

def fetch_page(url):
    try:
        start = time.time()
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        load = round((time.time() - start) * 1000)
        soup = BeautifulSoup(resp.text, "lxml")
        return resp, soup, load, None
    except Exception as e:
        return None, None, None, str(e)


# ─────────────────────────────────────────────
# ANALYSIS FUNCTIONS
# ─────────────────────────────────────────────

def check_domain(url):
    d = urlparse(url).netloc.lower()
    return {
        "domain": d,
        "is_https": url.startswith("https"),
        "is_free_platform": any(x in d for x in FREE_PLATFORMS),
        "platform_name": next((x for x in FREE_PLATFORMS if x in d), None),
    }


def check_contact(soup, html):
    html = html.lower()

    emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", html)

    return {
        "has_whatsapp": "whatsapp" in html,
        "has_contact_form": bool(soup.find("form")),
        "has_click_to_call": bool(soup.find("a", href=re.compile(r"^tel:"))),
    }


def check_technical(soup, load):
    return {
        "has_mobile_viewport": bool(soup.find("meta", {"name": "viewport"})),
        "has_favicon": bool(soup.find("link", rel=lambda x: x and "icon" in x)),
        "load_time_ms": load,
    }


def check_seo(soup):
    return {
        "has_title": bool(soup.title),
        "has_description": bool(soup.find("meta", {"name": "description"})),
        "has_h1": bool(soup.find("h1")),
    }


def check_marketing(html):
    html = html.lower()
    return {
        "has_cta": any(x in html for x in [
            "get a quote", "request a quote", "book now",
            "contact us", "call now", "whatsapp"
        ]),
        "has_testimonials": "testimonial" in html,
        "has_portfolio": "portfolio" in html,
        "has_social_links": any(x in html for x in [
            "facebook", "instagram", "linkedin"
        ]),
    }


def check_trust(html):
    html = html.lower()
    return {
        "has_privacy_policy": "privacy" in html,
    }


# ─────────────────────────────────────────────
# SCORING ENGINE (REALISTIC)
# ─────────────────────────────────────────────

def calculate_score(domain, contact, tech, seo, marketing, trust):
    score = 100
    issues = []

    def deduct(points, msg):
        nonlocal score
        score -= points
        issues.append(msg)

    if domain["is_free_platform"]:
        deduct(10, "Free platform domain")

    if not domain["is_https"]:
        deduct(10, "No HTTPS")

    if not contact["has_whatsapp"]:
        deduct(15, "No WhatsApp")

    if not contact["has_contact_form"]:
        deduct(10, "No contact form")

    if not contact["has_click_to_call"]:
        deduct(8, "No click-to-call")

    if not seo["has_title"]:
        deduct(8, "Missing title")

    if not seo["has_h1"]:
        deduct(8, "Missing H1")

    if not seo["has_description"]:
        deduct(6, "Missing meta description")

    if not marketing["has_cta"]:
        deduct(15, "Weak CTA")

    if not marketing["has_testimonials"]:
        deduct(10, "No testimonials")

    if not marketing["has_portfolio"]:
        deduct(10, "No portfolio")

    if not marketing["has_social_links"]:
        deduct(6, "No social links")

    if not trust["has_privacy_policy"]:
        deduct(5, "No privacy policy")

    return max(0, score), issues


# ─────────────────────────────────────────────
# MAIN AUDIT FUNCTION (IMPORT THIS ONLY)
# ─────────────────────────────────────────────

def audit(url: str, business_name=None):
    if not url.startswith("http"):
        url = "https://" + url

    resp, soup, load, err = fetch_page(url)

    if err:
        return {
            "url": url,
            "error": err,
            "score": 0
        }

    html = resp.text

    domain = check_domain(url)
    contact = check_contact(soup, html)
    tech = check_technical(soup, load)
    seo = check_seo(soup)
    marketing = check_marketing(html)
    trust = check_trust(html)

    score, issues = calculate_score(domain, contact, tech, seo, marketing, trust)

    return {
        "url": url,
        "business_name": business_name or domain["domain"],
        "score": score,
        "issues": issues,
        "load_time_ms": load,
        "timestamp": datetime.now().isoformat()
    }