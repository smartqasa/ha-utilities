"""Config flow for Scene Capture integration."""
import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

DOMAIN = "scene_capture"
_LOGGER = logging.getLogger(__name__)

class SceneCaptureConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Scene Capture."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the user-initiated flow."""
        if user_input is not None:
            return self.async_create_entry(title="Scene Capture", data={})

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({})
        )
