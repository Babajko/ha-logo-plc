"""Tests for the config flow (user step)."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.logo_plc.const import DOMAIN
from custom_components.logo_plc.hub import LogoConnectionError

# The integration targets Home Assistant 2024.6+; skip on older test
# environments that predate ConfigFlowResult.
pytestmark = pytest.mark.skipif(
    not hasattr(config_entries, "ConfigFlowResult"),
    reason="needs Home Assistant 2024.4+ (ConfigFlowResult)",
)

_USER_INPUT = {
    "name": "LOGO",
    "host": "192.168.0.2",
    "port": 502,
    "slave": 1,
    "scan_interval": 1,
}


async def test_user_flow_creates_entry(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    with (
        patch("custom_components.logo_plc.config_flow._test_connection"),
        patch("custom_components.logo_plc.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _USER_INPUT
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "LOGO"
    assert result["data"]["host"] == "192.168.0.2"


async def test_user_flow_cannot_connect(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "custom_components.logo_plc.config_flow._test_connection",
        side_effect=LogoConnectionError("no route"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _USER_INPUT
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
