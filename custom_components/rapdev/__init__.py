"""Example of a custom component exposing a service."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from datadog import initialize, statsd
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_PREFIX
from homeassistant.core import HomeAssistant, ServiceCall, callback, vol
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import state as state_helper

if TYPE_CHECKING:
    from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

CONF_RATE = "rate"
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8125
DEFAULT_PREFIX = "hass"
DEFAULT_RATE = 1
DOMAIN = "rapdev"

# Use empty_config_schema because the component does not have any config options
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_PREFIX, default=DEFAULT_PREFIX): cv.string,
                vol.Optional(CONF_RATE, default=DEFAULT_RATE): vol.All(
                    vol.Coerce(int), vol.Range(min=1)
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the an async service example component."""

    conf = config[DOMAIN]
    host = conf[CONF_HOST]
    port = conf[CONF_PORT]
    sample_rate = conf[CONF_RATE]
    prefix = conf[CONF_PREFIX]

    initialize(statsd_host=host, statsd_port=port)

    @callback
    def datadog_metric(call: ServiceCall) -> None:
        """Send metric to dogstatsd."""

        raw_tags = call.data.get("tags", {})
        metric = f"{prefix}.{call.data['metric']}"

        if isinstance(raw_tags, dict):
            tags = [f"{k}:{v}" for k, v in raw_tags.items()]
        elif isinstance(raw_tags, list):
            # validate they are formatted in k:v style
            for kv_pair in raw_tags:
                if len(kv_pair.split(":")) != 2:
                    _LOGGER.debug("improperly formatted tag: %s", kv_pair)
                    return
            tags = raw_tags

        try:
            value = state_helper.state_as_number(call.data["value"])
        except ValueError:
            _LOGGER.debug("Error sending %s: %s (tags: %s)", metric, value, tags)
            return

        statsd.gauge(metric=metric, value=value, tags=tags, sample_rate=sample_rate)
        _LOGGER.debug("Sent metric %s: %s (tags: %s)", metric, value, tags)

    # Register our service with Home Assistant.
    hass.services.async_register(
        DOMAIN,
        "send_to_datadog",
        datadog_metric,
        vol.Schema(
            {
                vol.Required("value"): vol.Coerce(float),
                vol.Optional("tags"): vol.Optional(vol.Schema(list[str])),
            }
        ),
    )

    # Return boolean to indicate that initialization was successfully.
    return True
