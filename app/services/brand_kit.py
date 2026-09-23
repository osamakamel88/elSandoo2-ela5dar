import json
import os
import re
import urllib.parse
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup
from loguru import logger
import requests

from app.config import config
from app.utils import utils

BRAND_KITS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "storage", "brand_kits")


def _get_storage_dir() -> str:
    os.makedirs(BRAND_KITS_DIR, exist_ok=True)
    return BRAND_KITS_DIR


def extract_brand_from_url(url: str, timeout: int = 15) -> Dict[str, Any]:
    """
    Extracts brand elements (Name, Logo, Colors, Fonts, Tone/Description) from a target website URL.
    Matches ImagineArt's 'Extract from Website' capability.
    """
    cleaned_url = url.strip()
    if not cleaned_url.startswith(("http://", "https://")):
        cleaned_url = f"https://{cleaned_url}"

    parsed = urllib.parse.urlparse(cleaned_url)
    domain = parsed.netloc.replace("www.", "")

    result: Dict[str, Any] = {
        "brand_name": domain.split(".")[0].capitalize(),
        "website_url": cleaned_url,
        "domain": domain,
        "logo_url": "",
        "colors": {
            "primary": "#22c55e",
            "secondary": "#0ea5e9",
            "accent": "#f59e0b",
            "background": "#0e1117",
        },
        "fonts": {
            "heading": "Montserrat",
            "body": "Inter",
        },
        "voice_and_tone": "",
        "tagline": "",
    }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        resp = requests.get(cleaned_url, headers=headers, proxies=config.proxy, timeout=timeout)
        if resp.status_code != 200:
            logger.warning(f"[BrandKit] URL {cleaned_url} returned status {resp.status_code}")
            return result

        html = resp.text
        soup = BeautifulSoup(html, "html.parser")

        # 1. Brand Name / Title
        og_site_name = soup.find("meta", property="og:site_name")
        if og_site_name and og_site_name.get("content"):
            result["brand_name"] = og_site_name["content"].strip()
        elif soup.title and soup.title.string:
            title_text = soup.title.string.strip()
            # Split common title separators like ' | ' or ' - '
            parts = re.split(r"[\s\|\-\:\—]+", title_text)
            if parts and parts[0]:
                result["brand_name"] = parts[0].strip()

        # 2. Tagline / Description
        meta_desc = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", property="og:description")
        if meta_desc and meta_desc.get("content"):
            result["tagline"] = meta_desc["content"].strip()[:200]
            result["voice_and_tone"] = f"Professional and informative. Core focus: {result['tagline'][:100]}"

        # 3. Logo URL
        logo_url = ""
        # Check og:image
        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"):
            logo_url = og_img["content"].strip()

        # Check apple-touch-icon
        if not logo_url:
            apple_icon = soup.find("link", rel=lambda r: r and "apple-touch-icon" in r.lower())
            if apple_icon and apple_icon.get("href"):
                logo_url = apple_icon["href"]

        # Check logo img tags
        if not logo_url:
            logo_img = soup.find("img", attrs={"alt": re.compile(r"logo", re.I)}) or soup.find("img", attrs={"class": re.compile(r"logo", re.I)})
            if logo_img and logo_img.get("src"):
                logo_url = logo_img["src"]

        # Check favicon
        if not logo_url:
            fav = soup.find("link", rel=lambda r: r and "icon" in r.lower())
            if fav and fav.get("href"):
                logo_url = fav["href"]

        if logo_url:
            result["logo_url"] = urllib.parse.urljoin(cleaned_url, logo_url)

        # 4. Colors extraction (from CSS style blocks, hex codes, or meta theme-color)
        theme_color = soup.find("meta", attrs={"name": "theme-color"})
        found_hex_colors = []
        if theme_color and theme_color.get("content"):
            color = theme_color["content"].strip()
            if color.startswith("#"):
                found_hex_colors.append(color.lower())

        # Scan for hex colors in style tags
        for style in soup.find_all("style"):
            css_text = style.string or ""
            hex_matches = re.findall(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b", css_text)
            for h in hex_matches:
                if len(h) == 7:
                    h_lower = h.lower()
                    if h_lower not in ("#ffffff", "#000000", "#111111", "#222222", "#cccccc", "#eeeeee"):
                        if h_lower not in found_hex_colors:
                            found_hex_colors.append(h_lower)

        if found_hex_colors:
            result["colors"]["primary"] = found_hex_colors[0]
            if len(found_hex_colors) > 1:
                result["colors"]["secondary"] = found_hex_colors[1]
            if len(found_hex_colors) > 2:
                result["colors"]["accent"] = found_hex_colors[2]

        # 5. Fonts extraction (look for Google Fonts or font-family in CSS)
        font_links = soup.find_all("link", href=re.compile(r"fonts\.googleapis\.com/css", re.I))
        for flink in font_links:
            href = flink.get("href", "")
            match = re.search(r"family=([^&:]+)", href)
            if match:
                font_name = match.group(1).replace("+", " ")
                result["fonts"]["heading"] = font_name
                break

    except Exception as e:
        logger.error(f"[BrandKit] Error extracting brand from {cleaned_url}: {e}")

    return result


def save_brand_kit(brand_id: str, data: Dict[str, Any]) -> str:
    """Saves a brand kit payload to storage/brand_kits/<brand_id>.json."""
    storage_dir = _get_storage_dir()
    clean_id = re.sub(r"[^\w\-]", "_", brand_id.strip()).lower()
    if not clean_id:
        clean_id = "default_brand"

    filepath = os.path.join(storage_dir, f"{clean_id}.json")
    data["brand_id"] = clean_id
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"[BrandKit] Saved brand kit {clean_id} to {filepath}")
    return filepath


def load_brand_kit(brand_id: str) -> Optional[Dict[str, Any]]:
    """Loads a brand kit by ID."""
    storage_dir = _get_storage_dir()
    clean_id = re.sub(r"[^\w\-]", "_", brand_id.strip()).lower()
    filepath = os.path.join(storage_dir, f"{clean_id}.json")
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"[BrandKit] Failed to load brand kit {clean_id}: {e}")
        return None


def list_brand_kits() -> List[Dict[str, Any]]:
    """Returns all saved brand kits."""
    storage_dir = _get_storage_dir()
    kits = []
    if not os.path.exists(storage_dir):
        return kits

    for fname in os.listdir(storage_dir):
        if fname.endswith(".json"):
            fpath = os.path.join(storage_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    kit = json.load(f)
                    kits.append(kit)
            except Exception as e:
                logger.warning(f"[BrandKit] Error reading {fpath}: {e}")
    return kits


def delete_brand_kit(brand_id: str) -> bool:
    """Deletes a brand kit by ID."""
    storage_dir = _get_storage_dir()
    clean_id = re.sub(r"[^\w\-]", "_", brand_id.strip()).lower()
    filepath = os.path.join(storage_dir, f"{clean_id}.json")
    if os.path.exists(filepath):
        os.remove(filepath)
        return True
    return False
