"""Reiri base entity."""
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

class ReiriEntity(CoordinatorEntity):
    """Base class for Reiri entities."""

    def __init__(self, coordinator, client, point_id, controller_device_id):
        """Initialize."""
        super().__init__(coordinator)
        self._client = client
        self._point_id = point_id
        self._controller_device_id = controller_device_id
        self._attr_unique_id = point_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return information to link this entity with the correct device."""
        point_data = self.coordinator.data.get(self._point_id, {})
        return DeviceInfo(
            identifiers={(DOMAIN, self._point_id)},
            name=point_data.get("name", self._point_id),
            manufacturer="Reiri",
            model="Air Conditioner",
            via_device_id=self._controller_device_id,
        )
