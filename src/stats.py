import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone

import aiohttp

logger = logging.getLogger(__name__)
_warned_missing_config = False
_warned_invalid_manual_users = False
EST = timezone(timedelta(hours=-5), name="EST")


def _get_gist_config() -> tuple[str, str, str] | None:
    global _warned_missing_config

    gist_id = os.getenv("GIST_ID")
    gist_token = os.getenv("GIST_TOKEN")
    gist_filename = os.getenv("GIST_FILENAME", "stats.json")

    if gist_id and gist_token:
        return gist_id, gist_token, gist_filename

    if not _warned_missing_config:
        logger.warning(
            "Stats update skipped: missing GIST_ID and/or GIST_TOKEN environment variable"
        )
        _warned_missing_config = True

    return None


def get_manual_users_count() -> int:
    global _warned_invalid_manual_users

    manual_users_raw = os.getenv("MANUAL_USERS", "0").strip()
    if not manual_users_raw:
        return 0

    try:
        manual_users = int(manual_users_raw)
    except ValueError:
        if not _warned_invalid_manual_users:
            logger.warning(
                "Invalid MANUAL_USERS value '%s'; defaulting to 0", manual_users_raw
            )
            _warned_invalid_manual_users = True
        return 0

    if manual_users < 0:
        if not _warned_invalid_manual_users:
            logger.warning(
                "Negative MANUAL_USERS value '%s'; defaulting to 0", manual_users_raw
            )
            _warned_invalid_manual_users = True
        return 0

    return manual_users

async def update_stats(
    *,
    users: int,
    guilds: int,
    guild_users: int,
    individual_users: int,
):
    gist_config = _get_gist_config()
    if gist_config is None:
        return False

    gist_id, gist_token, gist_filename = gist_config

    payload_content = json.dumps(
        {
            "users": users,
            "guilds": guilds,
            "guild_users": guild_users,
            "individual_users": individual_users,
            "updated_at": datetime.now(EST).strftime("%Y-%m-%d %I:%M:%S %p %Z"),
        },
        separators=(",", ":"),
    )

    payload = {
        "files": {
            gist_filename: {
                "content": payload_content
            }
        }
    }

    try:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.patch(
                f"https://api.github.com/gists/{gist_id}",
                headers={
                    "Authorization": f"Bearer {gist_token}",
                    "Accept": "application/vnd.github+json",
                },
                json=payload,
            ) as response:
                if response.status >= 400:
                    response_body = await response.text()
                    logger.error(
                        "Stats update failed status=%s gist_id=%s body=%s",
                        response.status,
                        gist_id,
                        response_body[:1000],
                    )
                response.raise_for_status()
    except Exception:
        logger.exception("Stats update request failed gist_id=%s", gist_id)
        return False

    return True

