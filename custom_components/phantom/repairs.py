"""Repairs handling for Phantom Power Monitoring integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Issue types
ISSUE_SENSOR_UNAVAILABLE = "sensor_unavailable"
ISSUE_UPSTREAM_UNAVAILABLE = "upstream_unavailable"
ISSUE_ALL_DEVICES_UNAVAILABLE = "all_devices_unavailable"


def async_create_sensor_unavailable_issue(
    hass: HomeAssistant,
    sensor_type: str,
    sensor_name: str,
    group_name: str,
    unavailable_entities: list[str],
) -> None:
    """Create an issue when sensors become unavailable."""
    issue_id = f"{sensor_type}_{group_name}_{sensor_name}"
    
    _LOGGER.debug(
        "Creating repair issue for unavailable sensor: %s (type: %s, group: %s)",
        sensor_name,
        sensor_type,
        group_name,
    )
    
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="sensor_unavailable",
        translation_placeholders={
            "sensor_name": sensor_name,
            "sensor_type": sensor_type,
            "group_name": group_name,
            "unavailable_count": str(len(unavailable_entities)),
            "unavailable_entities": ", ".join(unavailable_entities),
        },
        data={
            "sensor_type": sensor_type,
            "sensor_name": sensor_name,
            "group_name": group_name,
            "unavailable_entities": unavailable_entities,
        },
    )


def async_delete_sensor_unavailable_issue(
    hass: HomeAssistant,
    sensor_type: str,
    sensor_name: str,
    group_name: str,
) -> None:
    """Delete a sensor unavailable issue when it's resolved."""
    issue_id = f"{sensor_type}_{group_name}_{sensor_name}"
    
    _LOGGER.debug(
        "Deleting repair issue for sensor: %s (type: %s, group: %s)",
        sensor_name,
        sensor_type,
        group_name,
    )
    
    ir.async_delete_issue(hass, DOMAIN, issue_id)


def async_create_upstream_unavailable_issue(
    hass: HomeAssistant,
    group_name: str,
    upstream_entity: str,
) -> None:
    """Create an issue when upstream sensor becomes unavailable."""
    issue_id = f"upstream_{group_name}"
    
    _LOGGER.debug(
        "Creating repair issue for unavailable upstream sensor: %s (group: %s)",
        upstream_entity,
        group_name,
    )
    
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="upstream_unavailable",
        translation_placeholders={
            "group_name": group_name,
            "upstream_entity": upstream_entity,
        },
        data={
            "group_name": group_name,
            "upstream_entity": upstream_entity,
        },
    )


def async_delete_upstream_unavailable_issue(
    hass: HomeAssistant,
    group_name: str,
) -> None:
    """Delete an upstream unavailable issue when it's resolved."""
    issue_id = f"upstream_{group_name}"
    
    _LOGGER.debug(
        "Deleting repair issue for upstream sensor (group: %s)",
        group_name,
    )
    
    ir.async_delete_issue(hass, DOMAIN, issue_id)


def async_create_all_devices_unavailable_issue(
    hass: HomeAssistant,
    group_name: str,
    unavailable_devices: list[str],
) -> None:
    """Create an issue when all devices in a group become unavailable."""
    issue_id = f"all_devices_{group_name}"
    
    _LOGGER.warning(
        "Creating repair issue: All devices unavailable in group '%s': %s",
        group_name,
        unavailable_devices,
    )
    
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="all_devices_unavailable",
        translation_placeholders={
            "group_name": group_name,
            "device_count": str(len(unavailable_devices)),
            "device_list": ", ".join(unavailable_devices),
        },
        data={
            "group_name": group_name,
            "unavailable_devices": unavailable_devices,
        },
    )


def async_delete_all_devices_unavailable_issue(
    hass: HomeAssistant,
    group_name: str,
) -> None:
    """Delete an all devices unavailable issue when it's resolved."""
    issue_id = f"all_devices_{group_name}"
    
    _LOGGER.debug(
        "Deleting repair issue for all devices unavailable (group: %s)",
        group_name,
    )
    
    ir.async_delete_issue(hass, DOMAIN, issue_id)