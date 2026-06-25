import re
import time
from datetime import datetime
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": "Mozilla/5.0"
}
TIMEOUT = 15

WEIGHTS = {
    "no_whatsapp": 15,
    "gmail_email": 8,
    "no_contact_form": 5,
    "no_click_to_call": 5,
    "free_platform": 10,
    "no_https": 10,
    "no_cta": 10,
    "no_testimonials": 5,
    "no_portfolio": 5,
    "no_title": 5,
    "no_description": 3,
    "no_h1": 5,
    "old_copyright": 3,
    "no_privacy_policy": 3,
    "no_mobile_viewport": 8,
    "no_favicon": 2,
    "no_social_links": 3,
}


FREE_PLATFORMS = [
    "wixsite.com","wix.com","weebly.com","wordpress.com",
    "blogspot.com","godaddysites.com","squarespace.com",
]


def fetch_page(url):
    try:
        start = time.time()
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        load = round((time.time() - start) * 1000)
        soup = BeautifulSoup(resp.text, "lxml")
        return resp, soup, load, None
    except Exception as e:
        return None, None, None, str(e)


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
        "has_gmail": any("@gmail.com" in e for e in emails),
        "has_company_email": any("@gmail.com" not in e for e in emails),
        "has_contact_form": bool(soup.find("form")),
        "has_click_to_call": bool(soup.find("a", href=re.compile(r"^tel:")))
    }


def check_technical(soup, load):
    return {
        "has_mobile_viewport": bool(soup.find("meta", {"name": "viewport"})),
        "has_favicon": bool(soup.find("link", rel=lambda x: x and "icon" in x)),
        "load_time_ms": load
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
        "has_cta": any(x in html for x in ["contact", "quote", "book"]),
        "has_testimonials": "testimonial" in html,
        "has_portfolio": "portfolio" in html,
        "has_social_links": any(x in html for x in ["facebook", "instagram", "linkedin"]),
    }


def check_trust(html):
    html = html.lower()
    return {
        "has_privacy_policy": "privacy" in html,
        "old_copyright": False
    }


def calculate_score(domain, contact, tech, seo, marketing, trust):
    score = 100
    issues = []

    def deduct(k, msg):
        nonlocal score
        score -= WEIGHTS[k]
        issues.append(msg)

    if domain["is_free_platform"]:
        deduct("free_platform", "Free platform domain")

    if not domain["is_https"]:
        deduct("no_https", "No HTTPS")

    if not contact["has_whatsapp"]:
        deduct("no_whatsapp", "No WhatsApp")

    if not contact["has_contact_form"]:
        deduct("no_contact_form", "No contact form")

    if not seo["has_title"]:
        deduct("no_title", "No title")

    if not seo["has_h1"]:
        deduct("no_h1", "No H1")

    score = max(0, score)

    return score, issues


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