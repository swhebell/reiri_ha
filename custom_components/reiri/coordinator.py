"""DataUpdateCoordinator for Reiri integration."""
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .reiri_client import ReiriClient

_LOGGER = logging.getLogger(__name__)

class ReiriDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Reiri data."""

    def __init__(self, hass: HomeAssistant, client: ReiriClient):
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Reiri",
            update_interval=timedelta(seconds=30),
        )
        self.client = client

    async def _async_update_data(self):
        """Fetch data from Reiri controller."""
        try:
            return await self.client.get_point_list()
        except Exception as err:
            raise UpdateFailed(f"Error communicating with controller: {err}") from err
