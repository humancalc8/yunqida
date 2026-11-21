
"""
YUNQIDA official catalogue lookup.

Searches the official YUNQIDA product sitemap and its linked
product pages for an exact model-number match.

The importer:
- Uses authorized manufacturer catalogue access.
- Does not request or check robots.txt.
- Limits requests and adds a delay between product pages.
- Matches model numbers rather than guessing from product names.
- Extracts available descriptions and technical specifications.
- Collects product image and PDF datasheet URLs.
- Does not download or publish images automatically.
"""

import re
import time
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.yunqida-ne.com"
SITEMAP_URL = f"{BASE_URL}/sitemap.html"

MANUFACTURER = "Guangdong Yunqida New Energy Technology Co., Ltd."

USER_AGENT = "YunqidaKenyaProductImporter/1.0"

REQUEST_TIMEOUT = (8, 20)
REQUEST_DELAY = 0.75
MAX_PRODUCT_PAGES = 60

ALLOWED_HOSTS = {
    "www.yunqida-ne.com",
    "yunqida-ne.com",
}


class CatalogueLookupError(Exception):
    """Base exception for catalogue lookup errors."""


class ProductNotFound(CatalogueLookupError):
    """Raised when the exact model cannot be found."""


def normalize_model(value):
    """
    Normalize model numbers for comparison.

    Examples:
        YQD-256150-LFOESS -> YQD256150LFOESS
        yqd 256150 lfoess -> YQD256150LFOESS
    """
    return re.sub(r"[^A-Z0-9]", "", str(value).upper())


def clean_text(value):
    """Remove excessive whitespace from extracted text."""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _check_official_url(url):
    """Only allow requests to the official YUNQIDA website."""

    parsed = urlsplit(url)

    if (
        parsed.scheme != "https"
        or parsed.hostname not in ALLOWED_HOSTS
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
    ):
        raise CatalogueLookupError(
            "Only official YUNQIDA HTTPS pages are supported."
        )

    return url



def _fetch_page(session, url):
    """Fetch one approved official HTML page using browser-style headers."""

    _check_official_url(url)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/",
    }

    try:
        response = session.get(
            url,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=False,
        )

        # Do not follow redirects automatically.
        if response.is_redirect or response.is_permanent_redirect:
            location = response.headers.get("Location", "")

            if not location:
                raise CatalogueLookupError(
                    f"Manufacturer returned a redirect without "
                    f"a destination: {url}"
                )

            redirect_url = urljoin(url, location)
            _check_official_url(redirect_url)

            response = session.get(
                redirect_url,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=False,
            )

            if response.is_redirect or response.is_permanent_redirect:
                raise CatalogueLookupError(
                    f"Multiple redirects are not supported: {url}"
                )

        response.raise_for_status()

    except requests.RequestException as exc:
        status = getattr(
            getattr(exc, "response", None),
            "status_code",
            None,
        )

        if status:
            raise CatalogueLookupError(
                f"Manufacturer returned HTTP {status} for: {url}"
            ) from exc

        raise CatalogueLookupError(
            f"Could not retrieve manufacturer page: {url}. "
            f"Details: {exc}"
        ) from exc

    # Verify the final response URL.
    _check_official_url(response.url)

    content_type = response.headers.get(
        "Content-Type", ""
    ).lower()

    if "text/html" not in content_type:
        raise CatalogueLookupError(
            f"Expected an HTML product page, received: {content_type}"
        )

    return BeautifulSoup(response.text, "html.parser")


def _get_product_links(soup):
    """Collect product detail links from the official HTML sitemap."""

    links = []
    seen = set()

    for anchor in soup.select("a[href]"):

        href = clean_text(anchor.get("href"))

        if not href:
            continue

        absolute_url = urljoin(BASE_URL, href)

        try:
            _check_official_url(absolute_url)
        except CatalogueLookupError:
            continue

        parsed = urlsplit(absolute_url)

        if not parsed.path.lower().startswith("/products/"):
            continue

        if not parsed.path.lower().endswith(".html"):
            continue

        product_url = (
            f"https://www.yunqida-ne.com{parsed.path}"
        )

        if product_url not in seen:
            seen.add(product_url)
            links.append(product_url)

    return links[:MAX_PRODUCT_PAGES]



def _page_model_matches(soup, requested_model):
    """
    Verify the requested model against the actual product content.

    Prefer an exact match in a model-labelled specification row.
    Related-product links must never count as product matches.
    """

    model_key = normalize_model(requested_model)

    has_model_specification = False

    # First, inspect technical specification tables.
    for row in soup.find_all("tr"):

        cells = [
            clean_text(cell.get_text(" ", strip=True))
            for cell in row.find_all(["th", "td"])
        ]

        if not cells:
            continue

        normalized_cells = [
            normalize_model(cell)
            for cell in cells
        ]

        if "MODEL" in normalized_cells:
            has_model_specification = True

        for index, cell in enumerate(normalized_cells):

            if cell != model_key:
                continue

            preceding_cells = normalized_cells[:index]

            if "MODEL" in preceding_cells:
                return True

    # If the page has a model specification but it identifies
    # another model, do not accept a mention elsewhere.
    if has_model_specification:
        return False

    # Fallback for manufacturer pages without specification tables.
    # Exclude links so related products cannot produce false matches.
    page_parts = []

    for element in soup.find_all(string=True):

        if element.find_parent([
            "a",
            "script",
            "style",
            "noscript",
            "nav",
            "header",
            "footer",
            "aside",
        ]):
            continue

        page_parts.append(str(element))

    page_text = normalize_model(" ".join(page_parts))

    return model_key in page_text



def _get_page_title(soup):
    """Find the product page title."""

    heading = soup.find("h1")

    if heading:
        return clean_text(heading.get_text(" ", strip=True))

    meta_title = soup.find("meta", property="og:title")

    if meta_title:
        return clean_text(meta_title.get("content"))

    if soup.title:
        return clean_text(soup.title.get_text())

    return "YUNQIDA Product"



def _get_description(soup):
    """
    Extract the manufacturer's product introduction.

    The product title and model are separated from the
    description by a line break. Incomplete final sentences
    are removed rather than published as finished copy.
    """

    intro = soup.select_one(".product-intro")

    if intro:
        text_container = intro.select_one(".textWrap2")

        if text_container:
            parts = []

            for content in text_container.contents:
                if getattr(content, "name", None) == "br":
                    break

                if isinstance(content, str):
                    parts.append(content)

            # The first text before the line break is the title.
            # Extract the description after the line break.
            description_parts = []
            after_break = False

            for content in text_container.contents:

                if getattr(content, "name", None) == "br":
                    after_break = True
                    continue

                if after_break:
                    if isinstance(content, str):
                        description_parts.append(content)
                    else:
                        description_parts.append(
                            content.get_text(" ", strip=True)
                        )

            description = clean_text(
                " ".join(description_parts)
            )

            if description:
                # Remove an unfinished final sentence.
                if description.rstrip().endswith(
                    ("It", "it", "and", "or", "with", "the", "a")
                ):
                    last_sentence = max(
                        description.rfind("."),
                        description.rfind("!"),
                        description.rfind("?"),
                    )

                    description = (
                        description[:last_sentence + 1]
                        if last_sentence >= 0
                        else ""
                    )

                if len(description) >= 60:
                    return description

    # Do not fall back to page-wide paragraphs: they may contain
    # unrelated service, navigation or footer content.
    return ""

def _extract_specification_tables(soup, requested_model):
    """
    Extract technical specification rows.

    If a specification table contains multiple model columns,
    attempt to identify the column corresponding to the
    requested model.

    Original table values are preserved for review.
    """

    specifications = []
    selected_values = {}

    model_key = normalize_model(requested_model)

    for table in soup.find_all("table"):

        rows = []

        for tr in table.find_all("tr"):

            cells = [
                clean_text(cell.get_text(" ", strip=True))
                for cell in tr.find_all(["th", "td"])
            ]

            cells = [cell for cell in cells if cell]

            if len(cells) >= 2:
                rows.append(cells)

        if not rows:
            continue

        # Identify the requested model's column, if present.
        selected_column = None

        for cells in rows:

            for index, cell in enumerate(cells):

                if normalize_model(cell) == model_key:

                    preceding = [
                        item.lower() for item in cells[:index]
                    ]

                    if "model" in preceding:
                        header_count = (
                            len(preceding)
                            - preceding[::-1].index("model")
                        )
                    else:
                        header_count = 1

                    selected_column = max(
                        0,
                        index - header_count,
                    )

                    break

            if selected_column is not None:
                break

        for cells in rows:

            label = cells[0]
            values = cells[1:]

            # Skip model-heading rows.
            if any(
                normalize_model(value) == model_key
                for value in values
            ):
                continue

            if not values:
                continue

            if (
                selected_column is not None
                and selected_column < len(values)
            ):
                selected_value = values[selected_column]

            elif len(values) == 1:
                selected_value = values[0]

            else:
                selected_value = " | ".join(values)

            selected_values[label] = selected_value

            specifications.append({
                "name": label,
                "value": selected_value,
                "all_values": values,
            })

    return specifications, selected_values


def _extract_features(soup):
    """
    Extract only genuine manufacturer product features.

    Features are read from the product's dedicated feature
    content block. Navigation, footer links, contact details,
    related products and technical tables are excluded.
    """

    features = []
    seen = set()

    product_content = soup.select_one(
        ".product_detailWrap"
    )

    if not product_content:
        return features

    feature_container = product_content.select_one(
        ".con-tbody-text"
    )

    if not feature_container:
        return features

    for paragraph in feature_container.find_all("p"):

        value = clean_text(
            paragraph.get_text(" ", strip=True)
        )

        # Remove manufacturer numbering, e.g. 01.
        value = re.sub(
            r"^\s*\d{1,2}\s*[.、)]\s*",
            "",
            value,
        ).strip()

        if not 15 <= len(value) <= 300:
            continue

        key = value.casefold()

        if key in seen:
            continue

        seen.add(key)
        features.append(value)

    return features



def _extract_images(soup, page_url):
    """
    Collect product image URLs.

    These URLs are returned for review. This function does not
    download images or copy them into media storage.
    """

    candidates = []
    seen = set()

    # Prefer social preview image where available.
    for selector in (
        'meta[property="og:image"]',
        'meta[name="twitter:image"]',
    ):

        meta = soup.select_one(selector)

        if meta and meta.get("content"):

            image_url = urljoin(
                page_url,
                meta["content"],
            )

            if image_url not in seen:
                seen.add(image_url)
                candidates.append(image_url)

    # Collect gallery and product images.
    for image in soup.find_all("img"):

        source = (
            image.get("data-original")
            or image.get("data-src")
            or image.get("data-lazy-src")
            or image.get("src")
            or ""
        )

        source = clean_text(source)

        if not source or source.startswith("data:"):
            continue

        image_url = urljoin(page_url, source)
        parsed = urlsplit(image_url)

        if parsed.scheme not in ("http", "https"):
            continue

        if image_url in seen:
            continue

        description = (
            image.get("alt", "")
            + " "
            + source
        ).lower()

        excluded_terms = (
            "logo",
            "wechat",
            "whatsapp",
            "telephone",
            "favicon",
            "icon",
            "captcha",
        )

        if any(
            term in description
            for term in excluded_terms
        ):
            continue

        seen.add(image_url)
        candidates.append(image_url)

    return candidates[:10]


def _extract_datasheets(soup, page_url):
    """Find PDF datasheet links published on the product page."""

    links = []
    seen = set()

    for anchor in soup.select("a[href]"):

        href = clean_text(anchor.get("href"))

        if not href:
            continue

        absolute_url = urljoin(page_url, href)

        if not urlsplit(
            absolute_url
        ).path.lower().endswith(".pdf"):
            continue

        if absolute_url not in seen:
            seen.add(absolute_url)
            links.append(absolute_url)

    return links


def _find_spec_value(specifications, *keywords):
    """Find a specification using its published table label."""

    for item in specifications:

        label = item["name"].lower()

        if any(
            keyword in label
            for keyword in keywords
        ):
            return item["value"]

    return ""


def _guess_category(title):
    """
    Map the manufacturer's product name to existing Django choices.

    This is a classification based on the published product title,
    not a manufacturer-provided category identifier.
    """

    title = title.lower()

    if "battery" in title:
        return "battery"

    if any(
        term in title
        for term in (
            "50kw",
            "55kw",
            "60kw",
            "20kw",
            "241kwh",
            "commercial",
            "industrial",
        )
    ):
        return "commercial"

    if "inverter" in title:
        return "solar"

    return "residential"


def _build_product_data(soup, requested_model, page_url):
    """Build a structured result from a confirmed model match."""

    title = _get_page_title(soup)

    description = _get_description(soup)

    specifications, selected_values = (
        _extract_specification_tables(
            soup,
            requested_model,
        )
    )

    capacity = _find_spec_value(
        specifications,
        "battery energy",
        "nominal energy",
    )

    if not capacity:

        capacity_match = re.search(
            r"\b\d+(?:\.\d+)?\s*kwh\b",
            title + " " + description,
            flags=re.IGNORECASE,
        )

        if capacity_match:
            capacity = capacity_match.group(0)

    power = _find_spec_value(
        specifications,
        "rated output power",
        "rated power",
        "inverter power",
    )

    if not power:

        inverter_match = re.search(
            r"\b\d+(?:\.\d+)?\s*kw\b",
            description,
            flags=re.IGNORECASE,
        )

        if inverter_match:
            power = inverter_match.group(0)

    warranty = _find_spec_value(
        specifications,
        "warranty",
    )

    images = _extract_images(
        soup,
        page_url,
    )

    description = description or (
        f"{title}. Manufacturer specifications are available "
        "in the technical details."
    )
        # Keep the tagline within 200 characters without
    # cutting off an incomplete sentence.
    tagline = description

    if len(tagline) > 200:
        sentence_ends = [
            match.end()
            for match in re.finditer(
                r"[.!?](?=\s|$)",
                tagline[:200],
            )
        ]

        if sentence_ends:
            tagline = tagline[:sentence_ends[-1]]
        else:
            tagline = title[:200]

    return {
        "manufacturer": MANUFACTURER,
        "name": title[:120],
        "model_number": requested_model,
        "category": _guess_category(title),
        "tagline": tagline,
        "description": description,
        "capacity": capacity[:60],
        "power": power[:60],
        "warranty": warranty[:60],
        "image_url": images[0] if images else "",
        "image_urls": images,
        "source_url": page_url,
        "source_title": title,
        "datasheet_urls": _extract_datasheets(
            soup,
            page_url,
        ),
        "features": _extract_features(soup),
        "technical_specifications": specifications,
        "selected_specification_values": selected_values,
        "match_method": "exact_model_number",
        "match_verified": True,
        "warnings": [],
    }


def lookup_yunqida_model(model_number):
    """
    Search the official YUNQIDA sitemap for an exact model number.

    Usage:
        result = lookup_yunqida_model("YQD-256150-LFOESS")
    """

    model_number = clean_text(model_number)

    normalized = normalize_model(model_number)

    if len(normalized) < 5:
        raise CatalogueLookupError(
            "Enter a complete product model number."
        )

    session = requests.Session()

    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
    })

    try:

        # robots.txt verification intentionally removed.
        # Manufacturer authorization has been obtained.
        crawl_delay = REQUEST_DELAY

        sitemap = _fetch_page(
            session,
            SITEMAP_URL,
        )

        product_links = _get_product_links(sitemap)

        if not product_links:
            raise CatalogueLookupError(
                "No product detail links were found in the "
                "official YUNQIDA sitemap."
            )

        for index, product_url in enumerate(product_links):

            if index:
                time.sleep(crawl_delay)

            try:

                page = _fetch_page(
                    session,
                    product_url,
                )

            except CatalogueLookupError:
                # Skip unavailable product pages.
                continue

            if not _page_model_matches(
                page,
                model_number,
            ):
                continue

            return _build_product_data(
                page,
                model_number,
                product_url,
            )

        raise ProductNotFound(
            f"No exact manufacturer catalogue match was found "
            f"for model: {model_number}"
        )

    finally:
        session.close()
