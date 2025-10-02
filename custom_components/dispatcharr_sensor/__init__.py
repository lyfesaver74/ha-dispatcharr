"""The Dispatcharr Sensor integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import PLATFORMS

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Dispatcharr Sensor from a config entry."""
    # This is the correct method name: async_forward_entry_setups
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # The unload method name is different, which is confusing. This one is correct.
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)