"""URL normalisation for source records."""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .models import SourceRecord


TRACKING_PARAMETERS = {
    "gclid",
    "fbclid",
    "mc_cid",
    "mc_eid",
}


def normalize_url(url: str) -> str:
    """Return a conservative, consistent representation of an HTTP(S) URL."""

    try:
        parsed = urlsplit(url.strip())
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"Invalid URL: {url!r}") from exc

    scheme = parsed.scheme.lower()

    if scheme not in {"http", "https"}:
        raise ValueError("Only HTTP and HTTPS URLs are supported")

    if not hostname:
        raise ValueError("URL must contain a hostname")

    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URLs containing credentials are not supported")

    hostname = hostname.lower()

    # Preserve IPv6 hostname syntax.
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"

    # Default ports do not change the resource's URL identity.
    if port is not None:
        is_default_port = (
            (scheme == "http" and port == 80)
            or (scheme == "https" and port == 443)
        )

        netloc = hostname if is_default_port else f"{hostname}:{port}"
    else:
        netloc = hostname

    # Treat an empty path as the root path.
    path = parsed.path or "/"

    # Remove tracking parameters but preserve meaningful query parameters.
    query_parameters = parse_qsl(
        parsed.query,
        keep_blank_values=True,
    )

    filtered_parameters = [
        (key, value)
        for key, value in query_parameters
        if not key.lower().startswith("utm_")
        and key.lower() not in TRACKING_PARAMETERS
    ]

    query = urlencode(filtered_parameters)

    # URL fragments identify a page location, not a different HTTP resource.
    return urlunsplit((scheme, netloc, path, query, ""))


def canonical_url_for(record: SourceRecord) -> str:
    """Normalise the explicit canonical URL, or fall back to the source URL."""

    url = record.canonical_url or record.url
    return normalize_url(url)