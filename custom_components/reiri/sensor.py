"""Sensor platform for Reiri."""
import logging

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature
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
    """Set up the Reiri sensor platform."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    client = data["client"]

    if not coordinator.data:
        return

    entities = []
    for point_id, point_data in coordinator.data.items():
        if "otemp" in point_data:
            entities.append(ReiriOutdoorTempSensor(coordinator, client, point_id))

    async_add_entities(entities)


class ReiriOutdoorTempSensor(ReiriEntity, SensorEntity):
    """Outdoor Temperature Sensor."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator, client, point_id):
        """Initialize."""
        super().__init__(coordinator, client, point_id)
        # Use point_id + suffix for unique ID
        self._attr_unique_id = f"{point_id}_otemp"
        self._attr_name = f"{coordinator.data[point_id].get('name', point_id)} Outdoor Temperature"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        point_data = self.coordinator.data.get(self._point_id, {})
        val = point_data.get("otemp")
        # According to logs, otemp is an integer like 30 or 31
        return val
