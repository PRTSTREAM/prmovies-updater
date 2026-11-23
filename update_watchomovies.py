import os
import re
from urllib.parse import quote, urlparse
import requests
from bs4 import BeautifulSoup

DB_URL = os.environ["FIREBASE_DB_URL"].rstrip("/")
DB_SECRET = os.environ.get("FIREBASE_DB_SECRET", "").strip()
WORKER_URL = "https://bold-darkness-d959.poonamchouhan076.workers.dev/?site="
FIREBASE_NODE = "Watchomovies/Domain"


def firebase_url(path: str) -> str:
    url = f"{DB_URL}/{path.lstrip('/')}.json"
    if DB_SECRET:
        url += f"?auth={quote(DB_SECRET)}"
    return url


def normalize_root_domain(raw_url: str) -> str | None:
    if not raw_url:
        return None
    raw_url = raw_url.strip()
    if not raw_url.startswith(("http://", "https://")):
        raw_url = "https://" + raw_url
    parsed = urlparse(raw_url)
    if not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}/"


def extract_domain_from_html(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")

    # 1. Check meta property="og:url"
    meta_og_url = soup.find("meta", attrs={"property": "og:url"})
    if meta_og_url and meta_og_url.get("content"):
        found = normalize_root_domain(meta_og_url["content"])
        if found:
            return found

    # 2. Fallback: meta property="og:image" or link rel="canonical"
    meta_og_img = soup.find("meta", attrs={"property": "og:image"})
    if meta_og_img and meta_og_img.get("content"):
        found = normalize_root_domain(meta_og_img["content"])
        if found:
            return found

    canonical = soup.find("link", attrs={"rel": "canonical"})
    if canonical and canonical.get("href"):
        found = normalize_root_domain(canonical["href"])
        if found:
            return found

    # 3. Last fallback regex on og:url
    match = re.search(
        r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    )
    if match:
        return normalize_root_domain(match.group(1))

    return None


def main():
    # 1. Get current domain from Firebase -> Watchomovies/Domain
    res = requests.get(firebase_url(FIREBASE_NODE), timeout=20)
    res.raise_for_status()
    current_domain = res.json()
    print("Purana Domain (Firebase):", current_domain)

    if not current_domain:
        raise ValueError(f"Firebase mein {FIREBASE_NODE} khali hai ya mila nahi.")

    # 2. Fetch through worker
    target = WORKER_URL + quote(str(current_domain).strip(), safe="")
    print("Worker URL:", target)

    page_res = requests.get(target, timeout=30)
    page_res.raise_for_status()

    # 3. Extract new domain from meta property
    new_domain = extract_domain_from_html(page_res.text)
    print("Naya Domain (Meta se mila):", new_domain)

    if not new_domain:
        raise ValueError("HTML source mein meta property se domain nahi mila.")

    # 4. Update Firebase if changed
    if new_domain != str(current_domain).strip():
        put_res = requests.put(firebase_url(FIREBASE_NODE), json=new_domain, timeout=20)
        put_res.raise_for_status()
        print("Firebase update ho gaya! Naya value:", new_domain)
    else:
        print("Domain pehle se same hai, update ki zaroorat nahi.")


if __name__ == "__main__":
    main()
