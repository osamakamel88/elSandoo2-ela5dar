import html
import io
import json
import os
import re
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import requests
from loguru import logger
from PIL import Image

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

from app.utils import utils

# User-Agent simulating modern Chrome browser to minimize blocking
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,"
        "image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
    ),
    "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
    "Cache-Control": "max-age=0",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

_MIN_IMAGE_DIMENSION = 200  # Filter out small icons, logos, and tracking pixels
_MAX_IMAGES_TO_DOWNLOAD = 8


def fetch_url(url: str, timeout: int = 15) -> Tuple[str, str]:
    """
    Fetch the content of a URL using browser-like headers.
    Returns (html_content, final_url).
    """
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    session = requests.Session()
    session.headers.update(_BROWSER_HEADERS)

    # Specific oEmbed handling for known social networks (TikTok, Twitter/X)
    if "tiktok.com" in url:
        try:
            oembed_url = f"https://www.tiktok.com/oembed?url={urllib.parse.quote(url)}"
            resp = session.get(oembed_url, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                synthetic_html = f"""
                <html>
                <head>
                    <title>{html.escape(data.get('title', 'TikTok Video'))}</title>
                    <meta property="og:title" content="{html.escape(data.get('title', ''))}" />
                    <meta property="og:description" content="{html.escape(data.get('author_name', ''))} on TikTok" />
                    <meta property="og:image" content="{html.escape(data.get('thumbnail_url', ''))}" />
                </head>
                <body>
                    <h1>{html.escape(data.get('title', ''))}</h1>
                    <p>Author: {html.escape(data.get('author_name', ''))}</p>
                </body>
                </html>
                """
                return synthetic_html, url
        except Exception as exc:
            logger.debug(f"TikTok oEmbed fallback to standard fetch: {exc}")

    response = session.get(url, timeout=timeout, allow_redirects=True)
    response.raise_for_status()

    # Detect encoding
    if response.encoding is None or response.encoding.lower() == "iso-8859-1":
        response.encoding = response.apparent_encoding or "utf-8"

    return response.text, response.url


def clean_image_url(image_url: str, base_url: str) -> Optional[str]:
    """
    Resolve relative URLs and remove common thumbnail/compression filters
    to retrieve the highest resolution original image.
    """
    if not image_url or not isinstance(image_url, str):
        return None

    image_url = image_url.strip()
    if not image_url or image_url.startswith("data:"):
        return None

    # Resolve relative URL
    full_url = urllib.parse.urljoin(base_url, image_url)

    # Discard non-HTTP or SVG/GIF URLs
    lower = full_url.lower()
    if not lower.startswith(("http://", "https://")):
        return None
    if ".svg" in lower or ".gif" in lower or "icon" in lower or "logo" in lower:
        return None

    # Amazon high-res upgrade: strip sizing modifier like "._AC_SX679_."
    amazon_match = re.search(r"\._AC_[A-Za-z0-9_,]+_\.", full_url)
    if amazon_match:
        full_url = full_url.replace(amazon_match.group(0), ".")
    amazon_sy = re.search(r"\._[A-Z]{2}[0-9]+_\.", full_url)
    if amazon_sy:
        full_url = full_url.replace(amazon_sy.group(0), ".")

    # Shopify thumbnail upgrade: remove _small, _medium, _100x100 before extension
    full_url = re.sub(r"_(?:small|medium|compact|thumb|100x100|200x200)\.([a-zA-Z0-9]+)$", r".\1", full_url)

    # AliExpress thumbnail upgrade
    full_url = re.sub(r"_\d+x\d+\.jpg.*$", "", full_url)

    return full_url


def extract_product_or_post_info(url: str, html_text: str) -> Dict[str, Any]:
    """
    Extract product or social post details (title, description, price, features, images)
    using JSON-LD Schema.org, OpenGraph, Twitter Cards, and HTML structure.
    """
    info: Dict[str, Any] = {
        "url": url,
        "title": "",
        "description": "",
        "price": "",
        "currency": "",
        "brand": "",
        "features": [],
        "image_urls": [],
        "platform": "",
    }

    # Identify platform
    domain = urllib.parse.urlparse(url).netloc.lower()
    if "amazon" in domain:
        info["platform"] = "Amazon"
    elif "noon" in domain:
        info["platform"] = "Noon"
    elif "tiktok" in domain:
        info["platform"] = "TikTok"
    elif "instagram" in domain:
        info["platform"] = "Instagram"
    elif "twitter" in domain or "x.com" in domain:
        info["platform"] = "X (Twitter)"
    elif "shopify" in domain or "myshopify" in domain:
        info["platform"] = "Shopify Store"
    elif "aliexpress" in domain:
        info["platform"] = "AliExpress"
    else:
        info["platform"] = domain.replace("www.", "")

    # 1. Parse JSON-LD metadata
    json_ld_matches = re.findall(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_text,
        re.DOTALL | re.IGNORECASE,
    )
    for raw_json in json_ld_matches:
        try:
            data = json.loads(raw_json.strip())
            items = data if isinstance(data, list) else [data]
            for item in items:
                item_type = str(item.get("@type", "")).lower()
                if any(t in item_type for t in ["product", "newsarticle", "socialmediaposting", "article", "offer"]):
                    if not info["title"] and item.get("name"):
                        info["title"] = str(item["name"]).strip()
                    if not info["description"] and item.get("description"):
                        info["description"] = str(item["description"]).strip()
                    if not info["brand"] and item.get("brand"):
                        brand_val = item["brand"]
                        info["brand"] = brand_val.get("name", "") if isinstance(brand_val, dict) else str(brand_val)

                    # Extract price from offers
                    offers = item.get("offers")
                    if offers:
                        offer_list = offers if isinstance(offers, list) else [offers]
                        for off in offer_list:
                            if isinstance(off, dict):
                                if not info["price"] and off.get("price"):
                                    info["price"] = str(off["price"]).strip()
                                if not info["currency"] and off.get("priceCurrency"):
                                    info["currency"] = str(off["priceCurrency"]).strip()

                    # Extract images
                    images = item.get("image")
                    if images:
                        if isinstance(images, str):
                            images = [images]
                        elif isinstance(images, dict) and images.get("url"):
                            images = [images["url"]]
                        if isinstance(images, list):
                            for img in images:
                                if isinstance(img, str):
                                    clean = clean_image_url(img, url)
                                    if clean and clean not in info["image_urls"]:
                                        info["image_urls"].append(clean)
        except Exception:
            pass

    # 2. Parse OpenGraph and Meta tags
    meta_patterns = [
        (r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', "title"),
        (r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']', "title"),
        (r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']', "description"),
        (r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:description["\']', "description"),
        (r'<meta[^>]+name=["\']twitter:title["\'][^>]+content=["\']([^"\']+)["\']', "title"),
        (r'<meta[^>]+name=["\']twitter:description["\'][^>]+content=["\']([^"\']+)["\']', "description"),
        (r'<meta[^>]+property=["\']product:price:amount["\'][^>]+content=["\']([^"\']+)["\']', "price"),
        (r'<meta[^>]+property=["\']product:price:currency["\'][^>]+content=["\']([^"\']+)["\']', "currency"),
    ]
    for pattern, field in meta_patterns:
        if not info[field]:
            m = re.search(pattern, html_text, re.IGNORECASE)
            if m:
                info[field] = html.unescape(m.group(1)).strip()

    # OpenGraph & Twitter Images
    image_meta_patterns = [
        r'<meta[^>]+property=["\']og:image(?::secure_url)?["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image(?::secure_url)?["\']',
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
    ]
    for p in image_meta_patterns:
        for match in re.finditer(p, html_text, re.IGNORECASE):
            clean = clean_image_url(html.unescape(match.group(1)), url)
            if clean and clean not in info["image_urls"]:
                info["image_urls"].append(clean)

    # 3. HTML parsing (using BeautifulSoup if available, else regex)
    if BeautifulSoup:
        soup = BeautifulSoup(html_text, "html.parser")
        if not info["title"]:
            title_tag = soup.find("h1") or soup.find("title")
            if title_tag:
                info["title"] = title_tag.get_text(strip=True)

        if not info["description"]:
            desc_meta = soup.find("meta", attrs={"name": re.compile(r"description", re.I)})
            if desc_meta and desc_meta.get("content"):
                info["description"] = desc_meta["content"].strip()

        # Product feature bullets (Amazon #feature-bullets, generic ul.features)
        bullet_containers = soup.select("#feature-bullets ul li, .product-features li, ul.features li, .product-description li")
        for b in bullet_containers[:6]:
            txt = b.get_text(strip=True)
            if len(txt) > 5 and not txt.startswith("P.when"):
                info["features"].append(txt)

        # Scrape high-res product gallery <img> tags
        img_tags = soup.find_all("img")
        for img in img_tags:
            src = (
                img.get("data-old-hires")
                or img.get("data-high-res-image")
                or img.get("data-zoom-image")
                or img.get("data-src")
                or img.get("src")
            )
            if src:
                clean = clean_image_url(src, url)
                if clean and clean not in info["image_urls"]:
                    info["image_urls"].append(clean)
    else:
        # Fallback regex parsing
        if not info["title"]:
            m_title = re.search(r"<title[^>]*>(.*?)</title>", html_text, re.DOTALL | re.IGNORECASE)
            if m_title:
                info["title"] = html.unescape(m_title.group(1)).strip()

        # Regex image extraction
        for m_img in re.finditer(r'<img[^>]+src=["\']([^"\']+)["\']', html_text, re.IGNORECASE):
            clean = clean_image_url(m_img.group(1), url)
            if clean and clean not in info["image_urls"]:
                info["image_urls"].append(clean)

    # Clean title (e.g. remove "Amazon.com: ", "| Noon", etc.)
    if info["title"]:
        info["title"] = re.sub(
            r"^(?:Amazon(?:\.[a-z]+)?:\s*|Buy\s+|Purchase\s+)",
            "",
            info["title"],
            flags=re.IGNORECASE,
        )
        info["title"] = re.sub(
            r"\s*(?:\||-)\s*(?:Amazon|Noon|AliExpress|Shopify|Walmart|eBay).*$",
            "",
            info["title"],
            flags=re.IGNORECASE,
        ).strip()

    logger.info(
        f"Extracted info from {url}: Title='{info['title'][:50]}...', "
        f"Price='{info['price']} {info['currency']}', Images={len(info['image_urls'])}"
    )
    return info


def download_and_stage_images(
    image_urls: List[str],
    max_images: int = _MAX_IMAGES_TO_DOWNLOAD,
) -> List[Dict[str, Any]]:
    """
    Download product images, validate dimensions (>= 200x200),
    convert to RGB JPG, save into storage/local_videos/, and return
    a list of persisted material entries ready for VideoParams.
    """
    staged_materials: List[Dict[str, Any]] = []
    local_dir = utils.storage_dir("local_videos", create=True)

    session = requests.Session()
    session.headers.update(_BROWSER_HEADERS)

    count = 0
    for img_url in image_urls:
        if count >= max_images:
            break
        try:
            resp = session.get(img_url, timeout=12)
            if resp.status_code != 200 or not resp.content:
                continue

            # Verify image format and minimum size with PIL
            img = Image.open(io.BytesIO(resp.content))
            width, height = img.size

            if width < _MIN_IMAGE_DIMENSION or height < _MIN_IMAGE_DIMENSION:
                continue

            # Convert to RGB (in case of RGBA / CMYK)
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGB")
            elif img.mode != "RGB":
                img = img.convert("RGB")

            filename = f"product_asset_{uuid4().hex[:10]}.jpg"
            saved_path = os.path.join(local_dir, filename)

            img.save(saved_path, format="JPEG", quality=92)

            staged_materials.append({
                "provider": "local",
                "url": saved_path,
                "preview": saved_path,
                "filename": filename,
                "width": width,
                "height": height,
                "duration": 0,
            })
            count += 1
        except Exception as exc:
            logger.debug(f"Skipping image {img_url}: {exc}")
            continue

    logger.info(f"Successfully downloaded and staged {len(staged_materials)} product images.")
    return staged_materials


def build_product_script_prompt(
    product_info: Dict[str, Any],
    theme_context: str,
    language: str,
) -> str:
    """
    Build a structured, high-converting video script generation prompt
    combining the extracted product details, user's target theme, and language.
    """
    title = product_info.get("title", "")
    description = product_info.get("description", "")
    price = product_info.get("price", "")
    currency = product_info.get("currency", "")
    platform = product_info.get("platform", "")
    features = product_info.get("features", [])

    price_str = f"{price} {currency}".strip() if price else ""
    features_str = "\n- ".join(features) if features else ""

    theme_context = theme_context.strip() if theme_context else "Viral social media ad with high conversion"

    prompt = f"""
Write a high-converting, highly engaging short video narration script for a promotional video about this product / post.

PRODUCT / POST DETAILS:
- Name/Title: {title}
- Platform/Source: {platform}
{f'- Price: {price_str}' if price_str else ''}
{f'- Features:\n- {features_str}' if features_str else ''}
{f'- Overview: {description[:300]}' if description else ''}

TARGET THEME & CREATIVE CONTEXT:
"{theme_context}"

SCRIPTWRITING RULES:
1. Target Language: {language if language else 'Auto (Arabic or English as requested in theme)'}.
2. Structure:
   - [0-3s Hook]: A powerful scroll-stopping hook addressing the audience's problem or curiosity.
   - [4-15s Showcase]: Highlights key benefits, unique selling points, and emotional payoff (how it makes life easier/better).
   - [16-25s Call-to-Action]: Clear call to action (order now, link in bio, check out the deal).
3. Output format: Pure narration voiceover text ONLY. Do NOT include stage directions, timestamps, speaker labels (like [Narrator:] or [Music]), or markdown notes.
4. Keep the pace conversational, dynamic, and easy for text-to-speech to pronounce naturally.
"""
    return prompt.strip()


def synthesize_search_terms(product_info: Dict[str, Any]) -> List[str]:
    """
    Extract meaningful, visually descriptive search terms for stock video engines
    (Pexels, Pixabay) or AI image prompts based on product metadata.
    """
    title = (product_info.get("title") or "").lower()
    
    terms: List[str] = []
    
    # Check category cues
    if any(w in title for w in ["عرق", "deodorant", "تفتيح", "بشرة", "skin", "serum", "cream", "flawless", "fresh", "beauty"]):
        terms.extend(["skincare routine", "beauty cosmetic product", "natural skincare bottle", "clean glowing skin", "underarm brightening care", "luxury cosmetic packaging"])
    elif any(w in title for w in ["شعر", "hair", "shampoo", "oil", "زيت"]):
        terms.extend(["hair care routine", "healthy shiny hair", "hair serum cosmetic", "luxury hair oil"])
    elif any(w in title for w in ["عطر", "perfume", "fragrance", "oud", "مسك"]):
        terms.extend(["luxury perfume bottle", "fragrance spraying", "elegant aroma", "perfume commercial"])
    elif any(w in title for w in ["ساعة", "watch", "smartwatch"]):
        terms.extend(["smartwatch on wrist", "luxury wristwatch", "modern digital watch", "watch unboxing"])
    elif any(w in title for w in ["حذاء", "shoes", "sneakers", "شنطة", "bag", "فستان", "dress", "ملابس", "clothes"]):
        terms.extend(["fashion outfit showcase", "stylish apparel", "trendy model clothes", "fashion shopping review"])
    elif any(w in title for w in ["سماعة", "headphone", "earbuds", "phone", "هاتف", "شاحن", "charger"]):
        terms.extend(["modern wireless earbuds", "tech lifestyle product", "sleek gadget close up", "electronics unboxing"])
    else:
        # Generic high-converting commercial footage
        terms.extend(["modern product showcase", "unboxing aesthetic review", "customer shopping online", "commercial product shot", "lifestyle commercial promo"])

    # Add 1-2 words from title if ASCII or clean
    ascii_words = [w for w in re.findall(r"[a-zA-Z]{3,}", product_info.get("title", "")) if w.lower() not in ["and", "for", "with", "the", "products"]]
    for w in ascii_words[:2]:
        terms.append(f"{w} product")

    return terms[:8]


def synthesize_product_script(
    product_info: Dict[str, Any],
    theme_context: str = "",
    language: str = "",
) -> str:
    """
    Algorithmically synthesize a punchy, high-converting promotional script
    from product specs (title, features, price, platform, and creative theme).
    Guarantees the user always has a ready-to-render script even without an active LLM.
    """
    title = (product_info.get("title") or "هذا المنتج المميز").strip()
    price = str(product_info.get("price") or "").strip()
    currency = str(product_info.get("currency") or "EGP").strip()
    features = [f.strip() for f in product_info.get("features", []) if len(f.strip()) > 3]
    description = (product_info.get("description") or "").strip()

    # Determine language & dialect
    is_arabic = any('\u0600' <= char <= '\u06ff' for char in f"{title} {theme_context} {language}")
    theme_lower = theme_context.lower()
    is_egyptian = "مصر" in theme_context or "egyptian" in theme_lower
    is_gulf = "خليج" in theme_context or "gulf" in theme_lower or "saudi" in theme_lower

    if is_arabic:
        feature_text = ""
        if features:
            if len(features) >= 2:
                feature_text = f"بيتميز بـ {features[0]}، وكمان {features[1]}." if is_egyptian else f"يتميز بـ {features[0]}، بالإضافة إلى {features[1]}."
            else:
                feature_text = f"بيتميز بـ {features[0]}." if is_egyptian else f"يتميز بـ {features[0]}."
        elif description:
            desc_snippet = description[:90].rstrip("،.,; ")
            feature_text = f"معروف إنه {desc_snippet}." if is_egyptian else f"يقدم {desc_snippet}."

        price_text = ""
        if price:
            if is_egyptian:
                curr_name = "جنيه" if currency in ("EGP", "جنيه") else currency
                price_text = f"ودلوقتي عليه عرض خاص بـ {price} {curr_name} بس لفترة محدودة!"
            elif is_gulf:
                curr_name = "ريال" if currency in ("SAR", "ريال") else currency
                price_text = f"والحين متوفر بعرض استثنائي بسعر {price} {curr_name} فقط!"
            else:
                price_text = f"ومتوفر الآن بعرض خاص بسعر {price} {currency} فقط لفترة محدودة!"

        if is_egyptian:
            script_parts = [
                f"لو بتدوري على النتيجة المضمونة والانتعاش الحقيقي، {title} هو الاختيار اللي هيغير روتينك تماماً!",
                feature_text,
                "المنتج متجرب وبيفرق في روتينك اليومي من أول أسبوع.",
                price_text,
                "اطلبي دلوقتي من الرابط المباشر واستفيدي بالخصم قبل نفاذ الكمية!"
            ]
        elif is_gulf:
            script_parts = [
                f"تبين العناية المتكاملة والنتيجة اللي تبهرك؟ {title} هو الحل المثالي لجمالك وروتينك اليومي!",
                feature_text,
                "جودة ممتازة وفرق واضح من أول استخدام.",
                price_text,
                "اطلبي الحين عبر الرابط قبل نفاد الكمية!"
            ]
        else:
            script_parts = [
                f"اكتشفوا الحل الأمثل والفعّال للعناية مع {title}!",
                feature_text,
                "تركيبة متطورة تمنحكم عناية فائقة ونتائج ملموسة من أول تجربة.",
                price_text,
                "احصلوا عليه الآن بسهولة عبر الرابط واستمتعوا بالعرض الحصري!"
            ]
    else:
        # English
        feature_text = ""
        if features:
            if len(features) >= 2:
                feature_text = f"It features {features[0]}, plus {features[1]}."
            else:
                feature_text = f"It features {features[0]}."
        elif description:
            feature_text = f"Known for {description[:90].strip()}."

        price_text = f"And right now you can get it for just {price} {currency} on special offer!" if price else "Available now on a limited-time special offer!"

        script_parts = [
            f"Stop scrolling! If you want real, noticeable results, the {title} is an absolute game-changer!",
            feature_text,
            "Experience premium quality that upgrades your daily routine from day one.",
            price_text,
            "Click the link to order yours today before stock runs out!"
        ]

    clean_parts = [p.strip() for p in script_parts if p and p.strip()]
    return " ".join(clean_parts)


def generate_product_script(
    product_info: Dict[str, Any],
    theme_context: str = "",
    language: str = "",
    app_config=None,
) -> str:
    """
    Generate promotional script using the project's LLM engine.
    Gracefully falls back to high-converting template synthesis if LLM fails or is unavailable.
    """
    from app.services import llm

    prompt = build_product_script_prompt(
        product_info=product_info,
        theme_context=theme_context,
        language=language,
    )
    title = product_info.get("title", "")
    logger.info(f"generating product video script: title='{title[:40]}', theme='{theme_context[:40]}'")

    final_script = ""
    for i in range(2):
        try:
            if hasattr(llm, "_generate_response"):
                if app_config is None:
                    response = llm._generate_response(prompt=prompt)
                else:
                    response = llm._generate_response(prompt=prompt, app_config=app_config)
            elif hasattr(llm, "generate_script"):
                response = llm.generate_script(
                    video_subject=f"{title} - {theme_context}",
                    language=language,
                    video_script_prompt=prompt,
                    app_config=app_config,
                )
            else:
                response = ""

            if response and not response.strip().startswith("Error:"):
                cleaned = response.replace("*", "").replace("#", "")
                cleaned = re.sub(r"\[.*?\]", "", cleaned)
                cleaned = re.sub(r"\(.*?\)", "", cleaned)
                final_script = cleaned.strip()

            if final_script:
                break
        except Exception as exc:
            logger.warning(f"LLM script generation attempt {i+1} failed: {exc}")

    # Fallback to intelligent synthesis if LLM failed, returned error, or empty
    if not final_script:
        logger.info("Using intelligent template script synthesis for product video.")
        final_script = synthesize_product_script(
            product_info=product_info,
            theme_context=theme_context,
            language=language,
        )

    return final_script.strip()

