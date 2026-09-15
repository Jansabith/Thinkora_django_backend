"""Turn a YouTube link into an address that can be shown inside our page (an embed URL)."""

import re

# Finds the 11-character video id in the usual YouTube link formats:
#   https://www.youtube.com/watch?v=ID     https://youtu.be/ID
#   https://www.youtube.com/embed/ID       https://www.youtube.com/shorts/ID
YOUTUBE_ID_PATTERN = re.compile(
    r'(?:youtube\.com/(?:watch\?(?:.*&)?v=|embed/|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})'
)


def get_embed_url(url):
    """Return a YouTube embed URL, or None if the link is not a YouTube video."""
    match = YOUTUBE_ID_PATTERN.search(url)
    if match is None:
        return None
    return f'https://www.youtube-nocookie.com/embed/{match.group(1)}'
