"""Climate platform for Reiri."""
import logging
import time
from typing import Any, Dict, List, Optional

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVAC_MODE_OFF,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_DRY,
    HVAC_MODE_AUTO,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_FAN_MODE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Map Reiri modes to HA modes
REIRI_TO_HA_MODE = {
    "C": HVAC_MODE_COOL,
    "H": HVAC_MODE_HEAT,
    "F": HVAC_MODE_FAN_ONLY,
    "D": HVAC_MODE_DRY,
    "A": HVAC_MODE_AUTO,
}

HA_TO_REIRI_MODE = {v: k for k, v in REIRI_TO_HA_MODE.items()}

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Reiri climate platform."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    client = data["client"]

    if not coordinator.data:
        _LOGGER.error("No points found")
        return

    entities = []
    for point_id, point_data in coordinator.data.items():
        # Filter for HVAC units (assuming all points are climate entities for now)
        if "name" in point_data:
            entities.append(ReiriClimate(coordinator, client, point_id))

    async_add_entities(entities)


class ReiriClimate(CoordinatorEntity, ClimateEntity):
    """Representation of a Reiri Climate Device."""

    def __init__(self, coordinator, client, point_id):
        """Initialize the climate device."""
        super().__init__(coordinator)
        self._client = client
        self._point_id = point_id
        self._attr_unique_id = point_id
        self._attr_temperature_unit = TEMP_CELSIUS
        self._attr_supported_features = SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE
        self._last_modification = {}
        self._update_attrs()

    @property
    def device_info(self):
        """Return information to link this entity with the correct device."""
        return {
            "identifiers": {(DOMAIN, self._point_id)},
            "name": self._attr_name,
            "manufacturer": "Reiri",
            "model": "Air Conditioner",
            "via_device": (DOMAIN, "controller"),
        }

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attrs()
        self.async_write_ha_state()

    def _update_attrs(self):
        """Update attributes from coordinator data."""
        point_data = self.coordinator.data.get(self._point_id, {})
        
        # Name
        self._attr_name = point_data.get("name", self._point_id)

        # Current Temperature
        val = point_data.get("val", 0)
        try:
            self._attr_current_temperature = float(val)
        except (ValueError, TypeError):
            self._attr_current_temperature = 0.0

        # HVAC Mode
        if time.time() - self._last_modification.get("hvac_mode", 0) > 60:
            if point_data.get("stat") == "off":
                self._attr_hvac_mode = HVAC_MODE_OFF
            else:
                mode = point_data.get("mode")
                self._attr_hvac_mode = REIRI_TO_HA_MODE.get(mode, HVAC_MODE_AUTO)

        # Target Temperature
        if time.time() - self._last_modification.get("target_temperature", 0) > 60:
            mode = point_data.get("mode")
            if mode == "C":
                sp = point_data.get("csp", 0)
            elif mode == "H":
                sp = point_data.get("hsp", 0)
            else:
                sp = point_data.get("sp", 0)
            
            try:
                self._attr_target_temperature = float(sp)
            except (ValueError, TypeError):
                self._attr_target_temperature = 0.0

        # Fan Mode
        if time.time() - self._last_modification.get("fan_mode", 0) > 60:
            val = point_data.get("fanstep")
            if val == "A": self._attr_fan_mode = "Auto"
            elif val == "L": self._attr_fan_mode = "Low"
            elif val == "LM": self._attr_fan_mode = "Medium Low"
            elif val == "M": self._attr_fan_mode = "Medium"
            elif val == "MH": self._attr_fan_mode = "Medium High"
            elif val == "H": self._attr_fan_mode = "High"
            else: self._attr_fan_mode = val

        # HVAC Modes List
        modes = [HVAC_MODE_OFF]
        caps = point_data.get("mode_cap", {})
        if caps.get("C"): modes.append(HVAC_MODE_COOL)
        if caps.get("H"): modes.append(HVAC_MODE_HEAT)
        if caps.get("F"): modes.append(HVAC_MODE_FAN_ONLY)
        if caps.get("D"): modes.append(HVAC_MODE_DRY)
        if caps.get("A"): modes.append(HVAC_MODE_AUTO)
        self._attr_hvac_modes = modes

        # Fan Modes List
        fan_caps = point_data.get("fanstep_cap", {})
        fan_modes = []
        if fan_caps.get("A"):
            fan_modes.append("Auto")
            
        steps = fan_caps.get("S", 0)
        if steps == 2:
            fan_modes.extend(["Low", "High"])
        elif steps == 3:
            fan_modes.extend(["Low", "Medium", "High"])
        elif steps == 5:
            fan_modes.extend(["Low", "Medium Low", "Medium", "Medium High", "High"])
        else:
            if steps >= 1: fan_modes.append("Low")
            if steps >= 2: fan_modes.append("High")
            if steps >= 3: fan_modes.append("Medium")
        self._attr_fan_modes = fan_modes

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        
        # Optimistic update
        self._last_modification["target_temperature"] = time.time()
        self._attr_target_temperature = temperature
        self.async_write_ha_state()
        
        point_data = self.coordinator.data.get(self._point_id, {})
        mode = point_data.get("mode")
        key = "sp"
        
        if mode == "C":
            key = "csp"
        elif mode == "H":
            key = "hsp"
            
        # Reiri expects float value as string, e.g. "24.0"
        await self._client.operate({self._point_id: {key: str(float(temperature))}})
        # Do NOT refresh immediately due to latency

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        # Optimistic update
        self._last_modification["hvac_mode"] = time.time()
        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()

        if hvac_mode == HVAC_MODE_OFF:
            await self._client.operate({self._point_id: {"stat": "off"}})
        else:
            reiri_mode = HA_TO_REIRI_MODE.get(hvac_mode)
            if reiri_mode:
                # Mode change works as single command, but ensure ON
                cmd = {"stat": "on", "mode": reiri_mode}
                await self._client.operate({self._point_id: cmd})
        # Do NOT refresh immediately due to latency

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        # Optimistic update
        self._last_modification["fan_mode"] = time.time()
        self._attr_fan_mode = fan_mode
        self.async_write_ha_state()

        # Map HA mode to Reiri string
        val = "A"
        if fan_mode == "Low": val = "L"
        elif fan_mode == "Medium Low": val = "LM"
        elif fan_mode == "Medium": val = "M"
        elif fan_mode == "Medium High": val = "MH"
        elif fan_mode == "High": val = "H"
        elif fan_mode == "Auto": val = "A"
        
        # Fan change works as single command
        cmd = {"fanstep": val}
        await self._client.operate({self._point_id: cmd})
        # Do NOT refresh immediately due to latency
