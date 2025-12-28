"""The Reiri integration."""
import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, CONF_IP_ADDRESS, CONF_USERNAME, CONF_PASSWORD, DEFAULT_PORT
from .reiri_client import ReiriClient
from .coordinator import ReiriDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["climate"]

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Reiri component."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Reiri from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    ip_address = entry.data[CONF_IP_ADDRESS]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    client = ReiriClient(ip_address, username, password, DEFAULT_PORT)

    try:
        await client.connect()
        if not await client.login():
            _LOGGER.error("Failed to login to Reiri controller")
            return False
    except Exception as e:
        _LOGGER.error(f"Error connecting to Reiri controller: {e}")
        raise ConfigEntryNotReady from e

    # Create coordinator
    coordinator = ReiriDataUpdateCoordinator(hass, client)
    
    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data["client"].close()

    return unload_ok
