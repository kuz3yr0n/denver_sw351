import asyncio
import logging

from bleak import BleakClient  # type: ignore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        #  logging.FileHandler("app.log")
    ]
)

logger = logging.getLogger(__name__)


class _BLENotification:
    async def send(self, message: str) -> None:
        logger.info(f"Connecting to {self.DEVICE_ADDRESS}...")

        async with BleakClient(self.DEVICE_ADDRESS) as client:
            logger.info(f"Connected to {self.DEVICE_NAME}")

            async def handle_response(_, data: bytearray):
                status = 'failed sending'

                if len(data) >= 13 and data[9] == 0:
                    status = 'was sent'

                logger.info(
                    f"Notification {status} to device {self.DEVICE_NAME}"
                )

            await client.start_notify(self.NOTIFY_CHAR_UUID, handle_response)
            await client.write_gatt_char(
                self.WRITE_CHAR_UUID,
                self.build_notification_message(message),
                response=False
            )
            await asyncio.sleep(.5)
            await client.stop_notify(self.NOTIFY_CHAR_UUID)
