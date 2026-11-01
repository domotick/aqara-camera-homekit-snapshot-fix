"""HomeKit Snapshot Fix.

Makes homekit_controller ask a camera for snapshots only at sizes it
advertises, so cards in `camera_view: auto` (and the snapshot service) stop
showing a broken picture on cameras that ignore arbitrary sizes (Aqara E1).

Nothing else: no stream, no go2rtc, no entities, no config. Enable with one
line in configuration.yaml:

    homekit_snapshot_fix:

The change is made to the HomeKitCamera class in memory and is undone if
Home Assistant stops the integration.
"""

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.importlib import async_import_module
from homeassistant.helpers.typing import ConfigType

from .sizes import camera_sizes, pick_size

DOMAIN = "homekit_snapshot_fix"
CAMERA_MODULE = "homeassistant.components.homekit_controller.camera"
SAVED = "_homekit_snapshot_fix_saved"

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Patch HomeKitCamera.async_camera_image."""
    try:
        module = await async_import_module(hass, CAMERA_MODULE)
    except ImportError:
        _LOGGER.error("HomeKit Controller isn't available; nothing to fix")
        return False
    cls = module.HomeKitCamera

    if getattr(cls, SAVED, None) is not None:
        _LOGGER.debug("Already patched")
        return True
    original = cls.async_camera_image
    setattr(cls, SAVED, original)

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        try:
            size = pick_size(camera_sizes(self), width, height)
        except Exception:  # noqa: BLE001
            _LOGGER.warning(
                "Couldn't read %s's advertised sizes", self.entity_id, exc_info=True
            )
            size = None
        if size is None:
            return await original(self, width, height)
        _LOGGER.debug(
            "%s: asked %sx%s, requesting %sx%s", self.entity_id, width, height, *size
        )
        image = await self._accessory.pairing.image(self._aid, *size)  # noqa: SLF001
        if image is None and size != (width, height):
            return await original(self, width, height)
        return image

    cls.async_camera_image = async_camera_image
    _LOGGER.info("HomeKit camera snapshots now use advertised sizes")
    return True
