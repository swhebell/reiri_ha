"""Config flow for Reiri integration."""
import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS, CONF_USERNAME, CONF_PASSWORD
from .const import DOMAIN, DEFAULT_PORT
from .reiri_client import LOGIN_BLOCKED, ReiriClient

_LOGGER = logging.getLogger(__name__)


class LoginBlocked(Exception):
    """The controller is temporarily blocking logins after a failed attempt."""


DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def _validate_input(ip_address: str, username: str, password: str) -> None:
    """Validate that we can connect and log in with the given credentials.

    Raises ConnectionError if the controller cannot be reached, PermissionError
    if the credentials are rejected and LoginBlocked if the controller is in its
    short lockout period after a failed attempt.
    """
    client = ReiriClient(ip_address, username, password, DEFAULT_PORT)

    try:
        await client.connect()
    except Exception as e:
        _LOGGER.error("Connection failed: %s", e)
        raise ConnectionError from e

    try:
        if not await client.login():
            if client.last_login_result == LOGIN_BLOCKED:
                raise LoginBlocked
            raise PermissionError("Login failed")
    except (PermissionError, LoginBlocked):
        raise
    except Exception as e:
        _LOGGER.error("Login error: %s", e)
        raise PermissionError from e
    finally:
        await client.close()


class ReiriConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Reiri."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            ip_address = user_input[CONF_IP_ADDRESS].strip()
            user_input[CONF_IP_ADDRESS] = ip_address

            await self.async_set_unique_id(ip_address)
            self._abort_if_unique_id_configured()

            try:
                await _validate_input(
                    ip_address, user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except PermissionError:
                errors["base"] = "invalid_auth"
            except LoginBlocked:
                errors["base"] = "login_blocked"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"Reiri ({ip_address})", data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]):
        """Handle re-authentication when the controller rejects our credentials."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Ask for new credentials and update the existing entry."""
        errors = {}
        reauth_entry = self._get_reauth_entry()
        ip_address = reauth_entry.data[CONF_IP_ADDRESS]

        if user_input is not None:
            try:
                await _validate_input(
                    ip_address, user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except PermissionError:
                errors["base"] = "invalid_auth"
            except LoginBlocked:
                errors["base"] = "login_blocked"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            description_placeholders={"ip_address": ip_address},
            errors=errors,
        )
