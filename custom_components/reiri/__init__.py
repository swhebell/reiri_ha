"""The Reiri integration."""
import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from homeassistant.helpers import device_registry as dr
from .const import DOMAIN, CONF_IP_ADDRESS, CONF_USERNAME, CONF_PASSWORD, DEFAULT_PORT
from .reiri_client import ReiriAuthError, ReiriClient
from .coordinator import ReiriDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["climate", "sensor", "binary_sensor"]

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Reiri component."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Reiri from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    ip_address = entry.data[CONF_IP_ADDRESS]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    # Entries created before 1.2.3 have no unique ID; adopt the IP so that
    # duplicate controllers are rejected by the config flow.
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(entry, unique_id=ip_address)

    client = ReiriClient(ip_address, username, password, DEFAULT_PORT)

    try:
        await client.connect()
    except Exception as e:
        _LOGGER.error("Error connecting to Reiri controller: %s", e)
        raise ConfigEntryNotReady from e

    try:
        login_ok = await client.login()
    except ReiriAuthError as e:
        await client.close()
        raise ConfigEntryNotReady(f"Login error: {e}") from e
    except Exception as e:
        await client.close()
        _LOGGER.error("Error logging in to Reiri controller: %s", e)
        raise ConfigEntryNotReady from e

    if not login_ok:
        await client.close()
        raise ConfigEntryAuthFailed("Reiri controller rejected the credentials")

    # Create coordinator
    coordinator = ReiriDataUpdateCoordinator(hass, client)
    
    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Register the controller device
    device_registry = dr.async_get(hass)
    controller_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "controller")},
        manufacturer="Reiri",
        name="Reiri Controller",
        model="Reiri Hub",
        configuration_url=f"http://{ip_address}",
    )

    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
        "controller_device_id": controller_device.id,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

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
