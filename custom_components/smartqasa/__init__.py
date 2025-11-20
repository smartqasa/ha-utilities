from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .services_config import register_config_services
from .services_scene import register_scene_services

async def async_setup(hass: HomeAssistant, config: ConfigType):
    """Set up the SmartQasa integration."""
    register_config_services(hass)
    register_scene_services(hass)

    hass.data.setdefault(DOMAIN, {})

    return True
