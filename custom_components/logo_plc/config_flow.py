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
from homeassistant.helpers import selector

from .const import (
    CONF_HOST,
    CONF_NAME,
    CONF_OUTPUTS,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    CONF_TYPE,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE,
    DOMAIN,
    TYPE_BUTTON,
    TYPE_IMPULSE_SWITCH,
    TYPE_LATCHING_SWITCH,
    TYPE_SENSOR,
    TYPE_SIMPLE_SWITCH,
)
from .hub import LogoError, LogoHub
from .models import clean_entity, entities_of, schema_for_type, validate_entity

TYPE_OPTIONS = [
    {"value": TYPE_SENSOR, "label": "State indicator (read-only)"},
    {"value": TYPE_BUTTON, "label": "Impulse button"},
    {"value": TYPE_IMPULSE_SWITCH, "label": "Impulse switch (reads Q, pulses)"},
    {"value": TYPE_LATCHING_SWITCH, "label": "Latching switch (reads Q, holds level)"},
    {"value": TYPE_SIMPLE_SWITCH, "label": "Simple switch (no feedback)"},
]

CONNECTION_SCHEMA = vol.Schema(
    {
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

    async def async_step_import(
        self, import_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Create or update an entry from a YAML `logo_plc:` block."""
        unique_id = f"{import_data[CONF_HOST]}:{import_data[CONF_PORT]}"
        connection = {
            CONF_NAME: import_data[CONF_NAME],
            CONF_HOST: import_data[CONF_HOST],
            CONF_PORT: import_data[CONF_PORT],
            CONF_SLAVE: import_data[CONF_SLAVE],
            CONF_SCAN_INTERVAL: import_data[CONF_SCAN_INTERVAL],
        }
        options = {CONF_OUTPUTS: import_data.get(CONF_OUTPUTS, [])}

        for entry in self._async_current_entries():
            if entry.unique_id == unique_id:
                changed = self.hass.config_entries.async_update_entry(
                    entry, data=connection, options=options
                )
                if changed:
                    self.hass.config_entries.async_schedule_reload(entry.entry_id)
                return self.async_abort(reason="already_configured")

        await self.async_set_unique_id(unique_id)
        return self.async_create_entry(
            title=import_data[CONF_NAME], data=connection, options=options
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return LogoOptionsFlow(config_entry)


class LogoOptionsFlow(OptionsFlow):
    """Edit the PLC connection and its entities from the UI."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._entry = config_entry
        self._entities: list[dict[str, Any]] = [
            dict(item) for item in entities_of(config_entry.options)
        ]
        self._connection: dict[str, Any] | None = None
        self._edit_index: int | None = None
        self._pending_type: str | None = None
        self._defaults: dict[str, Any] | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        menu = ["add"]
        if self._entities:
            menu += ["edit", "remove"]
        menu += ["edit_yaml", "connection", "save"]
        return self.async_show_menu(step_id="init", menu_options=menu)

    async def async_step_add(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._pending_type = user_input[CONF_TYPE]
            self._edit_index = None
            self._defaults = None
            return await self.async_step_entity_form()
        schema = vol.Schema(
            {
                vol.Required(CONF_TYPE, default=TYPE_IMPULSE_SWITCH): (
                    selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=TYPE_OPTIONS,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                )
            }
        )
        return self.async_show_form(step_id="add", data_schema=schema)

    async def async_step_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if not self._entities:
            return await self.async_step_init()
        if user_input is not None:
            index = int(user_input["target"])
            self._edit_index = index
            self._pending_type = self._entities[index][CONF_TYPE]
            self._defaults = self._entities[index]
            return await self.async_step_entity_form()
        choices = {
            str(index): f"{item[CONF_NAME]} ({item[CONF_TYPE]})"
            for index, item in enumerate(self._entities)
        }
        schema = vol.Schema({vol.Required("target"): vol.In(choices)})
        return self.async_show_form(step_id="edit", data_schema=schema)

    async def async_step_entity_form(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._pending_type is not None
        if user_input is not None:
            item = clean_entity(self._pending_type, user_input)
            if self._edit_index is None:
                self._entities.append(item)
            else:
                self._entities[self._edit_index] = item
            self._edit_index = None
            self._pending_type = None
            self._defaults = None
            return await self.async_step_init()
        schema = schema_for_type(self._pending_type)
        if self._defaults:
            schema = self.add_suggested_values_to_schema(schema, self._defaults)
        return self.async_show_form(
            step_id="entity_form",
            data_schema=schema,
            description_placeholders={"type": self._pending_type},
        )

    async def async_step_remove(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if not self._entities:
            return await self.async_step_init()
        if user_input is not None:
            drop = set(user_input.get("remove", []))
            self._entities = [
                item
                for index, item in enumerate(self._entities)
                if str(index) not in drop
            ]
            return await self.async_step_init()
        choices = {
            str(index): f"{item[CONF_NAME]} ({item[CONF_TYPE]})"
            for index, item in enumerate(self._entities)
        }
        schema = vol.Schema(
            {vol.Optional("remove", default=[]): cv.multi_select(choices)}
        )
        return self.async_show_form(step_id="remove", data_schema=schema)

    async def async_step_edit_yaml(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit the whole entity list in a YAML code editor."""
        errors: dict[str, str] = {}
        suggested: list[dict[str, Any]] = self._entities
        if user_input is not None:
            raw = user_input.get("entities")
            if raw is None:
                raw = []
            suggested = raw
            if not isinstance(raw, list):
                errors["base"] = "invalid_entities"
            else:
                try:
                    self._entities = [validate_entity(item) for item in raw]
                except vol.Invalid:
                    errors["base"] = "invalid_entities"
                else:
                    return await self.async_step_init()
        schema = self.add_suggested_values_to_schema(
            vol.Schema({vol.Required("entities"): selector.ObjectSelector()}),
            {"entities": suggested},
        )
        return self.async_show_form(
            step_id="edit_yaml", data_schema=schema, errors=errors
        )

    async def async_step_connection(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._connection = {**self._entry.data, **user_input}
            return await self.async_step_init()
        schema = self.add_suggested_values_to_schema(
            CONNECTION_SCHEMA, self._entry.data
        )
        return self.async_show_form(step_id="connection", data_schema=schema)

    async def async_step_save(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._connection is not None:
            self.hass.config_entries.async_update_entry(
                self._entry, data=self._connection
            )
        return self.async_create_entry(
            title="", data={CONF_OUTPUTS: self._entities}
        )
