import pytest
from app.utils.url_resolver import (
    clean_tracking_params,
    detect_platform,
    normalize_media_url,
)


def test_detect_platform():
    assert detect_platform("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "youtube"
    assert detect_platform("https://youtu.be/dQw4w9WgXcQ") == "youtube"
    assert detect_platform("https://www.instagram.com/reel/C3zY2XpL_9a/") == "instagram"
    assert detect_platform("https://www.tiktok.com/@user/video/7123456789") == "tiktok"
    assert detect_platform("https://vt.tiktok.com/ZS2xyz123/") == "tiktok"
    assert detect_platform("https://www.snapchat.com/spotlight/W7_ED1yoW_gAZlFXbA") == "snapchat"
    assert detect_platform("https://www.pinterest.com/pin/1234567890/") == "pinterest"
    assert detect_platform("https://pin.it/7xYz123") == "pinterest"
    assert detect_platform("https://example.com/video.mp4") == "general"


def test_clean_tracking_params():
    yt_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&si=abcdef123456&feature=shared"
    cleaned_yt = clean_tracking_params(yt_url)
    assert "v=dQw4w9WgXcQ" in cleaned_yt
    assert "si=" not in cleaned_yt
    assert "feature=" not in cleaned_yt

    ig_url = "https://www.instagram.com/reel/C3zY2XpL_9a/?igsh=MWQ1eDV6OWJ2aA=="
    cleaned_ig = clean_tracking_params(ig_url)
    assert "igsh=" not in cleaned_ig
    assert "https://www.instagram.com/reel/C3zY2XpL_9a/" in cleaned_ig


@pytest.mark.asyncio
async def test_normalize_media_url():
    url, platform = await normalize_media_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert "youtube.com" in url
    assert platform == "youtube"
