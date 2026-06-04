import os
import time
import hashlib


def fetch_with_cache(url: str, fetcher: callable, duration=3600) -> str:
    url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()
    cache_file = os.path.join("cache", f"{url_hash}")

    # Check if the cache file exists and is not too old
    if os.path.exists(cache_file) and (
        time.time() - os.path.getmtime(cache_file) < duration
    ):
        with open(cache_file, "r") as f:
            return f.read()

    result = fetcher(url)

    # Save the content to the cache file
    os.makedirs("cache", exist_ok=True)
    with open(cache_file, "w") as f:
        f.write(result)

    return result
