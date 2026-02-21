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
        self._base_interval = timedelta(seconds=30)
        super().__init__(
            hass,
            _LOGGER,
            name="Reiri",
            update_interval=self._base_interval,
        )
        self.client = client
        self._consecutive_failures: int = 0

    async def _async_update_data(self):
        """Fetch data from Reiri controller."""
        try:
            data = await self.client.get_point_list()
            if self._consecutive_failures > 0:
                _LOGGER.info(
                    "Reiri connection restored after %d failure(s)",
                    self._consecutive_failures,
                )
                self._consecutive_failures = 0
                self.update_interval = self._base_interval
            return data
        except Exception as err:
            self._consecutive_failures += 1
            log_fn = _LOGGER.error if self._consecutive_failures == 1 else _LOGGER.warning
            log_fn(
                "Error communicating with Reiri controller (attempt %d): %s",
                self._consecutive_failures,
                err,
            )
            # Exponential backoff: 30s → 60s → 120s → 240s → 300s max
            backoff = min(
                self._base_interval * (2 ** (self._consecutive_failures - 1)),
                timedelta(minutes=5),
            )
            self.update_interval = backoff
            raise UpdateFailed(str(err)) from err
