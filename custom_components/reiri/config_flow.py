"""Config flow for Reiri integration."""
import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS, CONF_USERNAME, CONF_PASSWORD
from .const import DOMAIN, DEFAULT_PORT
from .reiri_client import ReiriClient

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

class ReiriConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Reiri."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                info = await self._validate_input(user_input)
                return self.async_create_entry(title=info["title"], data=user_input)
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except PermissionError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def _validate_input(self, data):
        """Validate the user input allows us to connect."""
        client = ReiriClient(data[CONF_IP_ADDRESS], data[CONF_USERNAME], data[CONF_PASSWORD], DEFAULT_PORT)
        
        try:
            await client.connect()
        except Exception as e:
            _LOGGER.error(f"Connection failed: {e}")
            raise ConnectionError from e
        
        try:
            if not await client.login():
                raise PermissionError("Login failed")
        except PermissionError:
            raise
        except Exception as e:
            _LOGGER.error(f"Login error: {e}")
            raise PermissionError from e
        finally:
            await client.close()

        return {"title": f"Reiri ({data[CONF_IP_ADDRESS]})"}
