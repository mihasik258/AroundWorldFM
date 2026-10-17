import httpx
import pytest

from app.core.config import settings
from app.core.net import UnsafeURLError, ensure_public_host, outbound_client, validate_http_url
from app.services.now_playing_service import parse_stream_title


@pytest.fixture
def strict(monkeypatch):
    monkeypatch.setattr(settings, "ALLOW_PRIVATE_STREAM_HOSTS", False)


@pytest.mark.parametrize(
    "url",
    ["ftp://example.com/a", "javascript:alert(1)", "https://u:p@example.com", "//example.com"],
)
def test_validate_http_url_rejects(url):
    with pytest.raises(UnsafeURLError):
        validate_http_url(url)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "host",
    [
        "127.0.0.1",
        "10.0.0.5",
        "192.168.1.1",
        "169.254.169.254",
        "::1",
        "::ffff:127.0.0.1",
        "0.0.0.0",
    ],
)
async def test_private_hosts_blocked(strict, host):
    with pytest.raises(UnsafeURLError):
        await ensure_public_host(host, 80)


@pytest.mark.asyncio
async def test_localhost_name_blocked(strict):
    with pytest.raises(UnsafeURLError):
        await ensure_public_host("localhost", 80)


@pytest.mark.asyncio
async def test_public_ip_allowed(strict):
    await ensure_public_host("93.184.216.34", 443)


@pytest.mark.asyncio
async def test_redirect_to_private_host_is_blocked(strict):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "93.184.216.34":
            return httpx.Response(302, headers={"location": "http://127.0.0.1:5432/"})
        return httpx.Response(200)

    async with outbound_client(5.0, transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(UnsafeURLError):
            await client.get("http://93.184.216.34/stream")


@pytest.mark.parametrize(
    ("raw", "artist", "title"),
    [
        ("Moby - Everloving", "Moby", "Everloving"),
        ("Just A Title", None, "Just A Title"),
        ("Artist - Song - Remix", "Artist", "Song - Remix"),
    ],
)
def test_parse_stream_title(raw, artist, title):
    parsed = parse_stream_title(raw)
    assert parsed["artist"] == artist
    assert parsed["title"] == title
    assert parsed["spotify_url"].startswith("https://open.spotify.com/search/")


@pytest.mark.parametrize("raw", ["", "-", "Unknown", "  "])
def test_parse_stream_title_skips_junk(raw):
    assert parse_stream_title(raw) is None
