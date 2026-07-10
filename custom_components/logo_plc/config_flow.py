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
from homeassistant.data_entry_flow import section
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import (
    BINARY_SENSOR_DEVICE_CLASSES,
    CONF_AREA,
    CONF_CONTROL,
    CONF_DEVICE_CLASS,
    CONF_DOMAIN,
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
    CONF_WRITE_ADDRESS,
    CONTROLLABLE_DOMAINS,
    CTRL_IMPULSE,
    CTRL_LATCHING,
    CTRL_SIMPLE,
    DEFAULT_PORT,
    DEFAULT_PULSE_DURATION,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE,
    DOM_BINARY_SENSOR,
    DOM_BUTTON,
    DOM_FAN,
    DOM_LIGHT,
    DOM_SWITCH,
    DOMAIN,
    LOGO_Q_COUNT,
    SWITCH_DEVICE_CLASSES,
    q_to_state_coil,
)
from .hub import LogoError, LogoHub
from .models import clean_entity, entities_of, required_addresses, validate_entity

_MAX_COIL = 8319

DOMAIN_OPTIONS = [
    selector.SelectOptionDict(value=DOM_LIGHT, label="Light — lamp, LED, sconce"),
    selector.SelectOptionDict(value=DOM_FAN, label="Fan — exhaust, ventilation"),
    selector.SelectOptionDict(value=DOM_SWITCH, label="Switch — generic on/off load"),
    selector.SelectOptionDict(
        value=DOM_BINARY_SENSOR, label="Indicator — read-only state"
    ),
    selector.SelectOptionDict(value=DOM_BUTTON, label="Button — sends an impulse"),
]

CONTROL_OPTIONS = [
    selector.SelectOptionDict(
        value=CTRL_IMPULSE, label="Impulse — pulse a coil, read Q for state"
    ),
    selector.SelectOptionDict(
        value=CTRL_LATCHING, label="Latching — hold a coil level, read Q for state"
    ),
    selector.SelectOptionDict(
        value=CTRL_SIMPLE, label="Simple — hold a coil level, no feedback"
    ),
]


def _number(minimum: float, maximum: float, step: float, mode, unit=None):
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=minimum, max=maximum, step=step, mode=mode, unit_of_measurement=unit
        )
    )


def _q_selector() -> selector.SelectSelector:
    options = [
        selector.SelectOptionDict(
            value=str(q_to_state_coil(q)), label=f"Q{q} · coil {q_to_state_coil(q)}"
        )
        for q in range(1, LOGO_Q_COUNT + 1)
    ]
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=options,
            mode=selector.SelectSelectorMode.DROPDOWN,
            custom_value=True,
        )
    )


def _device_class_selector(domain: str) -> selector.SelectSelector:
    classes = (
        SWITCH_DEVICE_CLASSES
        if domain == DOM_SWITCH
        else BINARY_SENSOR_DEVICE_CLASSES
    )
    options = [
        selector.SelectOptionDict(value=c, label=c.replace("_", " ").capitalize())
        for c in classes
    ]
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=options, mode=selector.SelectSelectorMode.DROPDOWN
        )
    )


def _marker(marker, key: str, defaults: dict[str, Any], as_str: bool = False):
    value = defaults.get(key)
    if value is None:
        return marker(key)
    return marker(key, default=str(value) if as_str else value)


def _entity_schema(
    domain: str, control: str | None, defaults: dict[str, Any] | None
) -> vol.Schema:
    d = defaults or {}
    reqs = required_addresses(domain, control)
    fields: dict[Any, Any] = {
        vol.Required(CONF_NAME, default=d.get(CONF_NAME, "")): selector.TextSelector()
    }
    fields[_marker(vol.Optional, CONF_AREA, d)] = selector.AreaSelector()
    if CONF_STATE_ADDRESS in reqs:
        fields[_marker(vol.Required, CONF_STATE_ADDRESS, d, as_str=True)] = (
            _q_selector()
        )
    if CONF_PULSE_ADDRESS in reqs:
        fields[_marker(vol.Required, CONF_PULSE_ADDRESS, d)] = _number(
            0, _MAX_COIL, 1, selector.NumberSelectorMode.BOX
        )
    if CONF_WRITE_ADDRESS in reqs:
        fields[_marker(vol.Required, CONF_WRITE_ADDRESS, d)] = _number(
            0, _MAX_COIL, 1, selector.NumberSelectorMode.BOX
        )

    advanced: dict[Any, Any] = {}
    if CONF_PULSE_ADDRESS in reqs:
        advanced[
            vol.Optional(
                CONF_PULSE_DURATION,
                default=float(d.get(CONF_PULSE_DURATION, DEFAULT_PULSE_DURATION)),
            )
        ] = _number(0.1, 10, 0.1, selector.NumberSelectorMode.SLIDER, unit="s")
    advanced[_marker(vol.Optional, CONF_ICON, d)] = selector.IconSelector()
    if domain in (DOM_SWITCH, DOM_BINARY_SENSOR):
        advanced[_marker(vol.Optional, CONF_DEVICE_CLASS, d)] = (
            _device_class_selector(domain)
        )

    fields[vol.Required("advanced")] = section(
        vol.Schema(advanced), {"collapsed": True}
    )
    return vol.Schema(fields)


def _entity_label(item: dict[str, Any]) -> str:
    control = item.get(CONF_CONTROL)
    return f"{item[CONF_DOMAIN]}/{control}" if control else item[CONF_DOMAIN]


async def _test_connection(host: str, port: int, slave: int) -> None:
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
        self._domain: str | None = None
        self._control: str | None = None
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
            self._domain = user_input[CONF_DOMAIN]
            self._control = None
            self._edit_index = None
            self._defaults = None
            if self._domain in CONTROLLABLE_DOMAINS:
                return await self.async_step_control()
            return await self.async_step_entity_form()
        schema = vol.Schema(
            {
                vol.Required(CONF_DOMAIN, default=DOM_LIGHT): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=DOMAIN_OPTIONS, mode=selector.SelectSelectorMode.LIST
                    )
                )
            }
        )
        return self.async_show_form(step_id="add", data_schema=schema)

    async def async_step_control(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._control = user_input[CONF_CONTROL]
            return await self.async_step_entity_form()
        default = (self._defaults or {}).get(CONF_CONTROL, CTRL_IMPULSE)
        schema = vol.Schema(
            {
                vol.Required(CONF_CONTROL, default=default): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=CONTROL_OPTIONS, mode=selector.SelectSelectorMode.LIST
                    )
                )
            }
        )
        return self.async_show_form(step_id="control", data_schema=schema)

    async def async_step_entity_form(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._domain is not None
        if user_input is not None:
            data = dict(user_input)
            data.update(data.pop("advanced", {}))
            data[CONF_DOMAIN] = self._domain
            if self._control:
                data[CONF_CONTROL] = self._control
            item = clean_entity(data)
            if self._edit_index is None:
                self._entities.append(item)
            else:
                self._entities[self._edit_index] = item
            self._edit_index = None
            self._domain = None
            self._control = None
            self._defaults = None
            return await self.async_step_init()
        schema = _entity_schema(self._domain, self._control, self._defaults)
        return self.async_show_form(step_id="entity_form", data_schema=schema)

    async def async_step_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if not self._entities:
            return await self.async_step_init()
        if user_input is not None:
            index = int(user_input["target"])
            item = self._entities[index]
            self._edit_index = index
            self._domain = item[CONF_DOMAIN]
            self._control = item.get(CONF_CONTROL)
            self._defaults = item
            return await self.async_step_entity_form()
        choices = {
            str(index): f"{item[CONF_NAME]} ({_entity_label(item)})"
            for index, item in enumerate(self._entities)
        }
        schema = vol.Schema({vol.Required("target"): vol.In(choices)})
        return self.async_show_form(step_id="edit", data_schema=schema)

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
            str(index): f"{item[CONF_NAME]} ({_entity_label(item)})"
            for index, item in enumerate(self._entities)
        }
        schema = vol.Schema(
            {vol.Optional("remove", default=[]): cv.multi_select(choices)}
        )
        return self.async_show_form(step_id="remove", data_schema=schema)

    async def async_step_edit_yaml(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
            vol.Schema(
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
            ),
            self._entry.data,
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
