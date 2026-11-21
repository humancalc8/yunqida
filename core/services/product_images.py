
from io import BytesIO
from urllib.parse import urljoin, urlsplit

import requests
from PIL import Image, UnidentifiedImageError


ALLOWED_IMAGE_HOSTS = {
    "image.chukouplus.com",
}

IMAGE_TIMEOUT = (8, 20)
MAX_IMAGE_SIZE = 12 * 1024 * 1024  # 12 MB
MAX_PRODUCT_IMAGES = 10

USER_AGENT = "YunqidaKenyaProductImporter/1.0"

IMAGE_FORMATS = {
    "JPEG": "jpg",
    "PNG": "png",
    "WEBP": "webp",
}


class ProductImageDownloadError(Exception):
    """Raised when a manufacturer product image cannot be downloaded."""


def _validate_image_url(url):
    """Allow only HTTPS URLs from the approved manufacturer image host."""

    try:
        parsed = urlsplit(url)

        if (
            parsed.scheme.lower() != "https"
            or parsed.hostname not in ALLOWED_IMAGE_HOSTS
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
        ):
            raise ProductImageDownloadError(
                "Image URL is not from an approved manufacturer host."
            )

    except ValueError as exc:
        raise ProductImageDownloadError(
            "Invalid manufacturer image URL."
        ) from exc

    return url


def _read_image_response(response):
    """Read an image response without exceeding the configured size limit."""

    content_type = response.headers.get(
        "Content-Type", ""
    ).split(";")[0].strip().lower()

    if not content_type.startswith("image/"):
        raise ProductImageDownloadError(
            "The manufacturer URL did not return an image."
        )

    content_length = response.headers.get("Content-Length")

    if content_length:
        try:
            if int(content_length) > MAX_IMAGE_SIZE:
                raise ProductImageDownloadError(
                    "Image exceeds the 12 MB size limit."
                )
        except ValueError:
            pass

    chunks = []
    total_size = 0

    for chunk in response.iter_content(chunk_size=64 * 1024):
        if not chunk:
            continue

        total_size += len(chunk)

        if total_size > MAX_IMAGE_SIZE:
            raise ProductImageDownloadError(
                "Image exceeds the 12 MB size limit."
            )

        chunks.append(chunk)

    content = b"".join(chunks)

    if not content:
        raise ProductImageDownloadError("The downloaded image is empty.")

    try:
        image = Image.open(BytesIO(content))
        image_format = image.format
        image.verify()

    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
    ) as exc:
        raise ProductImageDownloadError(
            "The downloaded file is not a valid image."
        ) from exc

    extension = IMAGE_FORMATS.get(image_format)

    if not extension:
        raise ProductImageDownloadError(
            "Unsupported image format. JPEG, PNG and WEBP are supported."
        )

    return content, extension


def _download_one(session, original_url):
    """Download one image, validating every redirect."""

    current_url = _validate_image_url(original_url)

    for attempt in range(3):

        response = None

        try:
            response = session.get(
                current_url,
                timeout=IMAGE_TIMEOUT,
                allow_redirects=False,
                stream=True,
            )

            if response.status_code in (301, 302, 303, 307, 308):

                location = response.headers.get("Location")

                if not location:
                    raise ProductImageDownloadError(
                        "Image redirect did not provide a destination."
                    )

                if attempt >= 2:
                    raise ProductImageDownloadError(
                        "Too many image redirects."
                    )

                current_url = _validate_image_url(
                    urljoin(current_url, location)
                )

                continue

            response.raise_for_status()

            content, extension = _read_image_response(response)

            return {
                "content": content,
                "extension": extension,
                "source_url": original_url,
            }

        except requests.RequestException as exc:
            raise ProductImageDownloadError(
                f"Image request failed: {exc}"
            ) from exc

        finally:
            if response is not None:
                response.close()

    raise ProductImageDownloadError("Image download failed.")


def download_product_images(image_urls):
    """
    Download valid product images from approved manufacturer storage.

    Returns:
        downloaded: List of dictionaries containing image bytes,
                    extension and original source URL.
        errors: List of failed image URL messages.
    """

    downloaded = []
    errors = []
    seen = set()

    if not isinstance(image_urls, list):
        return downloaded, ["No valid image URL list was supplied."]

    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "image/avif,image/webp,image/png,image/jpeg,*/*",
    })

    try:
        for url in image_urls[:MAX_PRODUCT_IMAGES]:

            if not isinstance(url, str):
                continue

            url = url.strip()

            if not url or url in seen:
                continue

            seen.add(url)

            try:
                result = _download_one(session, url)
                result["filename"] = (
                    f"yunqida-product-{len(downloaded) + 1}."
                    f"{result['extension']}"
                )
                downloaded.append(result)

            except ProductImageDownloadError as exc:
                errors.append(f"{url}: {exc}")

    finally:
        session.close()

    return downloaded, errors
