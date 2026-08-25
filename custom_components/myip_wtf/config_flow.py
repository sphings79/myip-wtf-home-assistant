"""Config flow for the MyIP.wtf integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)
import voluptuous as vol

from .api import MyIpWtfClient, MyIpWtfError, MyIpWtfRateLimitError
from .const import (
    CONF_IPV4,
    CONF_IPV6,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TITLE,
    DOMAIN,
    IPV4,
    IPV6,
    MAX_SCAN_INTERVAL,
    MIN_INTERVAL_PER_VERSION,
)
from .coordinator import MyIpWtfConfigEntry
from .rate_limit import async_get_cache, async_get_limiter


def _schema(defaults: dict[str, Any]) -> vol.Schema:
    """Build the shared config/options schema."""
    return vol.Schema(
        {
            vol.Required(
                CONF_IPV4, default=defaults.get(CONF_IPV4, True)
            ): BooleanSelector(),
            vol.Required(
                CONF_IPV6, default=defaults.get(CONF_IPV6, True)
            ): BooleanSelector(),
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_INTERVAL_PER_VERSION,
                    max=MAX_SCAN_INTERVAL,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                    unit_of_measurement="min",
                )
            ),
        }
    )


def _validate(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate the user input against the upstream automation policy."""
    errors: dict[str, str] = {}
    enabled = [key for key in (CONF_IPV4, CONF_IPV6) if user_input.get(key)]
    if not enabled:
        errors["base"] = "no_ip_version"
        return errors

    # The service allows one request per minute in total.  Each enabled IP
    # version costs one request per polling cycle, so the interval has to grow
    # with the number of enabled versions.
    minimum = MIN_INTERVAL_PER_VERSION * len(enabled)
    if int(user_input[CONF_SCAN_INTERVAL]) < minimum:
        errors[CONF_SCAN_INTERVAL] = "interval_too_short"
    return errors


def _normalise(user_input: dict[str, Any]) -> dict[str, Any]:
    """Return the input with the interval stored as a plain integer."""
    return {
        CONF_IPV4: bool(user_input.get(CONF_IPV4)),
        CONF_IPV6: bool(user_input.get(CONF_IPV6)),
        CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
    }


class MyIpWtfConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = _validate(user_input)
            if not errors:
                options = _normalise(user_input)
                errors = await self._async_probe(options)
            if not errors:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=DEFAULT_TITLE, data={}, options=options
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                _schema({}), user_input or {}
            ),
            errors=errors,
            description_placeholders={"policy_url": "https://myip.wtf/automation"},
        )

    async def _async_probe(self, options: dict[str, Any]) -> dict[str, str]:
        """Check that the service answers for the first enabled IP version.

        Only one version is probed: a second request would have to wait for the
        shared one-request-per-minute slot and stall the setup dialog.
        """
        version = IPV4 if options[CONF_IPV4] else IPV6
        client = MyIpWtfClient(
            async_get_clientsession(self.hass),
            async_get_limiter(self.hass),
            cache=async_get_cache(self.hass),
        )
        try:
            await client.async_get(version)
        except MyIpWtfRateLimitError:
            return {"base": "rate_limited"}
        except MyIpWtfError:
            return {"base": "cannot_connect"}
        return {}

    @staticmethod
    @callback
    def async_get_options_flow(entry: MyIpWtfConfigEntry) -> MyIpWtfOptionsFlow:
        """Return the options flow."""
        return MyIpWtfOptionsFlow()


class MyIpWtfOptionsFlow(OptionsFlow):
    """Handle changes to an existing entry."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = _validate(user_input)
            if not errors:
                return self.async_create_entry(data=_normalise(user_input))

        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                _schema(current), user_input or current
            ),
            errors=errors,
            description_placeholders={"policy_url": "https://myip.wtf/automation"},
        )
