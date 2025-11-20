import json
import aiofiles
import os

from .const import (
    SQCONFIG_PATH,
    DEFAULT_CHANNEL,
    DEFAULT_AUTOUPDATE,
)


async def read_sqconfig() -> dict:
    """Read SmartQasa sqconfig.json."""

    if not os.path.exists(SQCONFIG_PATH):
        return {
            "channel": DEFAULT_CHANNEL,
            "autoUpdate": DEFAULT_AUTOUPDATE,
            "missing": True
        }

    try:
        async with aiofiles.open(SQCONFIG_PATH, "r", encoding="utf-8") as f:
            content = await f.read()
        return json.loads(content)
    except Exception as e:
        return {"error": f"Failed to read config: {e}"}


async def write_sqconfig(channel: str, autoUpdate: bool) -> dict:
    """Write SmartQasa sqconfig.json atomically."""

    cfg = {
        "channel": channel,
        "autoUpdate": bool(autoUpdate),
    }

    try:
        tmp = SQCONFIG_PATH + ".tmp"

        async with aiofiles.open(tmp, "w", encoding="utf-8") as f:
            await f.write(json.dumps(cfg, indent=2))

        os.replace(tmp, SQCONFIG_PATH)

        return {"success": True, "config": cfg}

    except Exception as e:
        return {"success": False, "error": str(e)}
