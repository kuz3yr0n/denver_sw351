from importlib import import_module
from platform import system

__all__ = ('BLENotification',)

try:
    module = import_module(f'.{system()}'.lower(), package=__package__)
except ImportError:
    pass

try:
    _BLENotification = module._BLENotification
except AttributeError:
    from .common import _BLENotification


class BLENotification(_BLENotification):
    DEVICE_ADDRESS = "MAC-ADDRESS"
    DEVICE_NAME = "SW-351"
    NOTIFY_CHAR_UUID = "long-string"
    WRITE_CHAR_UUID = "long-string"

    def __init__(
        self, device_address: str, device_name: str, notify_char_uuid: str,
        write_char_uuid: str
    ):
        self.DEVICE_ADDRESS = device_address
        self.DEVICE_NAME = device_name
        self.NOTIFY_CHAR_UUID = notify_char_uuid
        self.WRITE_CHAR_UUID = write_char_uuid

    def build_notification_message(
        self, text: str, unknown_field: int = None
    ) -> bytes:
        payload = text.encode("utf-16-le")

        if len(payload) > 254:
            raise ValueError(
                "Notification text is too long for the observed format"
            )

        inner = (
            bytes([0x06, 0x00, 0x60, 0x00])
            + bytes([(len(payload) + 1) & 0xFF, 0x0A])
            + payload
        )
        packet = (
            bytes([0xBA, 0x20])
            + len(inner).to_bytes(2, "big")
            + (unknown_field or 0x0000).to_bytes(2, "big")
            + 0x0F.to_bytes(2, "big")
            + inner
        )

        return packet
