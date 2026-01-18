"""Climate platform for Reiri."""
import logging
import time
from typing import Any, Dict, List, Optional

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVACMode,
    ClimateEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .entity import ReiriEntity

_LOGGER = logging.getLogger(__name__)

# Map Reiri modes to HA modes
# Map Reiri modes to HA modes
REIRI_TO_HA_MODE = {
    "C": HVACMode.COOL,
    "H": HVACMode.HEAT,
    "F": HVACMode.FAN_ONLY,
    "D": HVACMode.DRY,
    "A": HVACMode.AUTO,
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


class ReiriClimate(ReiriEntity, ClimateEntity):
    """Representation of a Reiri Climate Device."""

    def __init__(self, coordinator, client, point_id):
        """Initialize the climate device."""
        super().__init__(coordinator, client, point_id)
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
        self._last_modification = {}
        self._update_attrs()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attrs()
        self.async_write_ha_state()

    def _update_attrs(self):
        """Update attributes from coordinator data."""
        point_data = self.coordinator.data.get(self._point_id, {})
        # Debug logging removed

        
        # Name
        self._attr_name = point_data.get("name", self._point_id)

        # Current Temperature
        val = point_data.get("temp", 0)
        try:
            self._attr_current_temperature = float(val)
        except (ValueError, TypeError):
            self._attr_current_temperature = 0.0

        # HVAC Mode
        if time.time() - self._last_modification.get("hvac_mode", 0) > 60:
            if point_data.get("stat") == "off":
                self._attr_hvac_mode = HVACMode.OFF
            else:
                mode = point_data.get("mode")
                self._attr_hvac_mode = REIRI_TO_HA_MODE.get(mode, HVACMode.AUTO)

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
            if val == "A": self._attr_fan_mode = "auto"
            elif val == "L": self._attr_fan_mode = "low"
            elif val == "LM": self._attr_fan_mode = "medium-low"
            elif val == "M": self._attr_fan_mode = "medium"
            elif val == "MH": self._attr_fan_mode = "medium-high"
            elif val == "H": self._attr_fan_mode = "high"
            elif val: self._attr_fan_mode = val.lower()
            else: self._attr_fan_mode = None

        # Swing/Flap Mode
        if time.time() - self._last_modification.get("swing_mode", 0) > 60:
            val = point_data.get("flap")
            if val == "S":
                self._attr_swing_mode = "swing"
            elif val is not None:
                self._attr_swing_mode = str(val)
            else:
                self._attr_swing_mode = None

        # HVAC Modes List
        modes = [HVACMode.OFF]
        caps = point_data.get("mode_cap", {})
        if caps.get("C"): modes.append(HVACMode.COOL)
        if caps.get("H"): modes.append(HVACMode.HEAT)
        if caps.get("F"): modes.append(HVACMode.FAN_ONLY)
        if caps.get("D"): modes.append(HVACMode.DRY)
        if caps.get("A"): modes.append(HVACMode.AUTO)
        self._attr_hvac_modes = modes

        # Fan Modes List
        fan_caps = point_data.get("fanstep_cap", {})
        fan_modes = []
        if fan_caps.get("A"):
            fan_modes.append("auto")
            
        steps = fan_caps.get("S", 0)
        if steps == 2:
            fan_modes.extend(["low", "high"])
        elif steps == 3:
            fan_modes.extend(["low", "medium", "high"])
        elif steps == 5:
            fan_modes.extend(["low", "medium-low", "medium", "medium-high", "high"])
        else:
            if steps >= 1: fan_modes.append("low")
            if steps >= 2: fan_modes.append("high")
            if steps >= 3: fan_modes.append("medium")
        self._attr_fan_modes = fan_modes

        # Swing Modes List & Feature Support
        flap_caps = point_data.get("flap_cap", {})
        # Default to 3 if D is missing, similar to webapp, unless capabilities are totally missing
        # If flap_caps is empty, it might mean no info, assume supported or not?
        # Webapp says: if !isEmpty(point_info) -> check flap_cap.D.
        
        # We will assume supported if flap_cap is present or D is not 0.
        flap_steps = flap_caps.get("D", 3)
        
        if flap_steps == 0:
            # No flap control supported
            self._attr_supported_features &= ~ClimateEntityFeature.SWING_MODE
            self._attr_swing_modes = None
            self._attr_swing_mode = None
        else:
            # Flap control supported
            self._attr_supported_features |= ClimateEntityFeature.SWING_MODE
            
            swing_modes = ["swing"]
            # Explicit positions 0-4 (or up to steps?)
            # Webapp hardcodes logic for S -> 4 -> 3 -> 2 -> 1 -> 0.
            # We will expose 0 to 4. 
            # Note: The webapp logic cycles 4 down to 0 regardless of 'flap_steps' 
            # unless 'flap_steps' determines the range, but the loop just checks 'steps' for S toggle.
            # We will err on the side of exposing standard 5 steps if supported.
            swing_modes.extend([str(i) for i in range(5)]) 
            self._attr_swing_modes = swing_modes

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
        # Reiri expects float value as number, e.g. 24.0
        # Use 'sp' as the generic setpoint key, independent of mode
        await self._client.operate({self._point_id: {"sp": float(temperature)}})
        # Do NOT refresh immediately due to latency

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        # Optimistic update
        self._last_modification["hvac_mode"] = time.time()
        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()

        if hvac_mode == HVACMode.OFF:
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
        if fan_mode == "low": val = "L"
        elif fan_mode == "medium-low": val = "LM"
        elif fan_mode == "medium": val = "M"
        elif fan_mode == "medium-high": val = "MH"
        elif fan_mode == "high": val = "H"
        elif fan_mode == "auto": val = "A"
        
        # Fan change works as single command
        cmd = {"fanstep": val}
        await self._client.operate({self._point_id: cmd})
        # Do NOT refresh immediately due to latency

    async def async_set_swing_mode(self, swing_mode):
        """Set new target swing operation."""
        # Optimistic update
        self._last_modification["swing_mode"] = time.time()
        self._attr_swing_mode = swing_mode
        self.async_write_ha_state()

        val = "S"
        if swing_mode == "swing":
            val = "S"
        else:
            try:
                # Send integer for positions
                val = int(swing_mode)
            except ValueError:
                # Fallback to swing if invalid
                val = "S"
        
        cmd = {"flap": val}
        await self._client.operate({self._point_id: cmd})
