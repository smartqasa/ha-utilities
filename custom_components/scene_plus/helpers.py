from enum import Enum
from homeassistant.core import HomeAssistant
import logging

_LOGGER = logging.getLogger(__name__)


def safe_item(item):
    """Safe serialization for scenes."""
    try:
        if isinstance(item, Enum):
            return item.value
        if isinstance(item, (list, tuple, set)):
            return [safe_item(x) for x in item]
        if isinstance(item, dict):
            return {str(k): safe_item(v) for k, v in item.items()}
        return item
    except Exception as e:
        _LOGGER.warning(f"Failed to serialize item {item}: {e}")
        return None


async def retrieve_scene_id(hass: HomeAssistant, entity_id: str) -> str | None:
    """Get the internal scene ID field from a scene entity."""
    state = hass.states.get(entity_id)
    if not state:
        return None
    return state.attributes.get("id")
