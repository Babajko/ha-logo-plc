"""Config and options flow for the Siemens LOGO! PLC integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_DEVICE_CLASS,
    CONF_HOST,
    CONF_ICON,
    CONF_NAME,
    CONF_OUTPUTS,
    CONF_PORT,
    CONF_PULSE_ADDRESS,
    CONF_PULSE_DURATION,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    CONF_STATE_ADDRESS,
    DEFAULT_PORT,
    DEFAULT_PULSE_DURATION,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE,
    DOMAIN,
)
from .hub import LogoError, LogoHub

DEVICE_CLASSES = ["switch", "outlet"]


async def _test_connection(host: str, port: int, slave: int) -> None:
    """Open and close a connection, raising LogoError on failure."""
    hub = LogoHub(host, port=port, slave=slave)
    try:
        await hub.connect()
    finally:
        await hub.close()


class LogoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a LOGO! PLC."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
            )
            self._abort_if_unique_id_configured()
            try:
                await _test_connection(
                    user_input[CONF_HOST],
                    user_input[CONF_PORT],
                    user_input[CONF_SLAVE],
                )
            except LogoError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="LOGO"): str,
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Required(CONF_SLAVE, default=DEFAULT_SLAVE): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=247)
                ),
                vol.Required(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return LogoOptionsFlow(config_entry)


class LogoOptionsFlow(OptionsFlow):
    """Add, remove and save the PLC's outputs."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._entry = config_entry
        self._outputs: list[dict[str, Any]] = list(
            config_entry.options.get(CONF_OUTPUTS, [])
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="init", menu_options=["add", "remove", "save"]
        )

    async def async_step_add(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            output: dict[str, Any] = {
                CONF_NAME: user_input[CONF_NAME],
                CONF_STATE_ADDRESS: user_input[CONF_STATE_ADDRESS],
                CONF_PULSE_ADDRESS: user_input[CONF_PULSE_ADDRESS],
                CONF_PULSE_DURATION: user_input[CONF_PULSE_DURATION],
            }
            if user_input.get(CONF_ICON):
                output[CONF_ICON] = user_input[CONF_ICON]
            if user_input.get(CONF_DEVICE_CLASS):
                output[CONF_DEVICE_CLASS] = user_input[CONF_DEVICE_CLASS]
            self._outputs.append(output)
            return await self.async_step_init()

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_STATE_ADDRESS): vol.All(
                    vol.Coerce(int), vol.Range(min=0)
                ),
                vol.Required(CONF_PULSE_ADDRESS): vol.All(
                    vol.Coerce(int), vol.Range(min=0)
                ),
                vol.Required(
                    CONF_PULSE_DURATION, default=DEFAULT_PULSE_DURATION
                ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=10)),
                vol.Optional(CONF_ICON): str,
                vol.Optional(CONF_DEVICE_CLASS): vol.In(DEVICE_CLASSES),
            }
        )
        return self.async_show_form(step_id="add", data_schema=schema)

    async def async_step_remove(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if not self._outputs:
            return await self.async_step_init()
        if user_input is not None:
            drop = set(user_input.get("remove", []))
            self._outputs = [
                output
                for index, output in enumerate(self._outputs)
                if str(index) not in drop
            ]
            return await self.async_step_init()

        choices = {
            str(index): output[CONF_NAME]
            for index, output in enumerate(self._outputs)
        }
        schema = vol.Schema(
            {vol.Optional("remove", default=[]): cv.multi_select(choices)}
        )
        return self.async_show_form(step_id="remove", data_schema=schema)

    async def async_step_save(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_create_entry(
            title="", data={CONF_OUTPUTS: self._outputs}
        )
