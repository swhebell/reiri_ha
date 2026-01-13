"""Binary sensor platform for Reiri."""
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import ReiriEntity

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Reiri binary sensor platform."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    client = data["client"]

    if not coordinator.data:
        return

    entities = []
    for point_id, point_data in coordinator.data.items():
        if "filter" in point_data:
            entities.append(ReiriFilterBinarySensor(coordinator, client, point_id))
        
        if "thermo" in point_data:
            entities.append(ReiriCompressorBinarySensor(coordinator, client, point_id))

    async_add_entities(entities)


class ReiriFilterBinarySensor(ReiriEntity, BinarySensorEntity):
    """Filter Status Binary Sensor."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, client, point_id):
        """Initialize."""
        super().__init__(coordinator, client, point_id)
        self._attr_unique_id = f"{point_id}_filter"
        self._attr_name = f"{coordinator.data[point_id].get('name', point_id)} Filter"

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        point_data = self.coordinator.data.get(self._point_id, {})
        val = point_data.get("filter")
        # "on" means filter needs cleaning (problem)
        return val == "on"

class ReiriCompressorBinarySensor(ReiriEntity, BinarySensorEntity):
    """Compressor/Thermostat Status Binary Sensor."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator, client, point_id):
        """Initialize."""
        super().__init__(coordinator, client, point_id)
        self._attr_unique_id = f"{point_id}_compressor"
        self._attr_name = f"{coordinator.data[point_id].get('name', point_id)} Compressor"

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        point_data = self.coordinator.data.get(self._point_id, {})
        val = point_data.get("thermo")
        # "on" means compressor is running
        return val == "on"
