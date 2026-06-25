import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

TIMEOUT = 15

FREE_PLATFORMS = [
    "wixsite.com", "wix.com",
    "weebly.com",
    "wordpress.com",
    "blogspot.com",
    "godaddysites.com",
    "squarespace.com",
    "site123.me",
    "webnode.com",
]

CTA_KEYWORDS = ["get a quote", "book", "contact", "call", "whatsapp", "enquire"]
WHATSAPP_PATTERNS = [r"wa\.me", r"whatsapp", r"api\.whatsapp\.com"]


WEIGHTS = {
    "no_whatsapp": 15,
    "free_platform": 10,
    "no_https": 10,
    "no_contact_form": 5,
    "no_click_to_call": 5,
    "no_title": 5,
    "no_description": 3,
    "no_h1": 5,
}


# ---------------- FETCH ----------------

def fetch_page(url):
    try:
        start = time.time()
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        load_time = round((time.time() - start) * 1000)
        soup = BeautifulSoup(resp.text, "lxml")
        return resp, soup, load_time, None
    except Exception as e:
        return None, None, None, str(e)


# ---------------- CHECKS ----------------

def check_domain(url):
    p = urlparse(url)
    domain = p.netloc.lower()

    return {
        "domain": domain,
        "is_https": p.scheme == "https",
        "is_free_platform": any(x in domain for x in FREE_PLATFORMS),
        "platform_name": next((x for x in FREE_PLATFORMS if x in domain), None),
    }


def check_contact(soup, html):
    html_lower = html.lower()

    has_whatsapp = any(re.search(p, html_lower) for p in WHATSAPP_PATTERNS)
    forms = soup.find_all("form")
    tel_links = soup.find_all("a", href=re.compile(r"^tel:"))

    return {
        "has_whatsapp": has_whatsapp,
        "has_contact_form": len(forms) > 0,
        "has_click_to_call": len(tel_links) > 0,
    }


def check_seo(soup):
    title = soup.find("title")
    h1 = soup.find("h1")
    desc = soup.find("meta", attrs={"name": "description"})

    return {
        "has_title": bool(title),
        "has_h1": bool(h1),
        "has_description": bool(desc and desc.get("content")),
    }


# ---------------- SCORING ----------------

def calculate_score(domain, contact, seo):
    score = 100
    issues = []

    def deduct(key, msg):
        nonlocal score
        score -= WEIGHTS[key]
        issues.append(msg)

    if domain["is_free_platform"]:
        deduct("free_platform", "Free platform site")

    if not domain["is_https"]:
        deduct("no_https", "No HTTPS")

    if not contact["has_whatsapp"]:
        deduct("no_whatsapp", "No WhatsApp button")

    if not contact["has_contact_form"]:
        deduct("no_contact_form", "No contact form")

    if not contact["has_click_to_call"]:
        deduct("no_click_to_call", "No click-to-call")

    if not seo["has_title"]:
        deduct("no_title", "Missing title")

    if not seo["has_h1"]:
        deduct("no_h1", "Missing H1")

    if not seo["has_description"]:
        deduct("no_description", "Missing meta description")

    return max(score, 0), issues


def rating(score):
    if score <= 35:
        return "HOT"
    elif score <= 55:
        return "STRONG"
    elif score <= 70:
        return "MEDIUM"
    elif score <= 85:
        return "LOW"
    return "WEAK"


# ---------------- MAIN FUNCTION ----------------

def audit(url: str, business_name: str = None):
    if not url.startswith("http"):
        url = "https://" + url

    resp, soup, load_time, error = fetch_page(url)

    if error or not soup:
        return {
            "url": url,
            "error": error,
            "score": 0,
            "issues": ["Could not load site"]
        }

    html = resp.text

    domain = check_domain(url)
    contact = check_contact(soup, html)
    seo = check_seo(soup)

    score, issues = calculate_score(domain, contact, seo)

    return {
        "url": url,
        "business_name": business_name or domain["domain"],
        "score": score,
        "rating": rating(score),
        "issues": issues,
        "load_time_ms": load_time,
        "timestamp": datetime.now().isoformat()
    }