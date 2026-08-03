import asyncio
import logging
import threading
import time
from android.permissions import Permission
from .asyncio_permissions import request_permissions
from jnius import autoclass, PythonJavaClass, java_method  # type: ignore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        #  logging.FileHandler("app.log")
    ]
)

logger = logging.getLogger(__name__)

CCCD_UUID = "00002902-0000-1000-8000-00805f9b34fb"

BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
BluetoothDevice = autoclass('android.bluetooth.BluetoothDevice')
BluetoothGatt = autoclass('android.bluetooth.BluetoothGatt')
BluetoothGattCharacteristic = autoclass(
    'android.bluetooth.BluetoothGattCharacteristic'
)
BluetoothGattDescriptor = autoclass(
    'android.bluetooth.BluetoothGattDescriptor'
)
UUID = autoclass('java.util.UUID')
PythonActivity = autoclass('org.kivy.android.PythonActivity')
PyGattCallback = autoclass('org.kivy.android.PyGattCallback')

WRITE_TYPE_NO_RESPONSE = BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE
NOTIFICATION_ENABLE = BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE

Handler = autoclass('android.os.Handler')
Looper = autoclass('android.os.Looper')

_main_handler = Handler(Looper.getMainLooper())


class _MainThreadRunnable(PythonJavaClass):
    __javainterfaces__ = ['java/lang/Runnable']
    run_fn = None

    @java_method('()V')
    def run(self):
        if self.run_fn is not None:
            self.run_fn()


def run_on_main_thread(fn, timeout=10.0):
    done = threading.Event()
    outcome = {}

    def _wrapper():
        try:
            outcome['value'] = fn()
        except Exception as exc:  # noqa: BLE001
            outcome['error'] = exc
        finally:
            done.set()

    runnable = _MainThreadRunnable()
    runnable.run_fn = _wrapper
    _main_handler.post(runnable)

    if not done.wait(timeout):
        raise TimeoutError("Main-thread BLE operation timed out")
    if 'error' in outcome:
        raise outcome['error']
    return outcome.get('value')


def _to_java_bytes(data: bytes):
    return list(data)


class GattListener(PythonJavaClass):
    __javacontext__ = 'app'
    __javainterfaces__ = ['org/kivy/android/PyGattCallback$PyGattListener']
    DEVICE_NAME = None
    on_connected = None
    on_descriptor_write = None
    on_notify = None
    on_services_discovered = None
    on_write = None

    @java_method('(Landroid/bluetooth/BluetoothGatt;II)V')
    def onConnectionStateChange(self, gatt, status, new_state):
        self.on_connected(new_state == 2, status)

    @java_method('(Landroid/bluetooth/BluetoothGatt;I)V')
    def onServicesDiscovered(self, gatt, status):
        self.on_services_discovered(status == 0)

    @java_method('(Landroid/bluetooth/BluetoothGatt;Landroid/bluetooth/'
                 'BluetoothGattCharacteristic;I)V')
    def onCharacteristicWrite(self, gatt, characteristic, status):
        self.on_write(status == 0)

    @java_method('(Landroid/bluetooth/BluetoothGatt;Landroid/bluetooth/'
                 'BluetoothGattDescriptor;I)V')
    def onDescriptorWrite(self, gatt, descriptor, status):
        self.on_descriptor_write(status == 0)

    @java_method('(Landroid/bluetooth/BluetoothGatt;Landroid/bluetooth/'
                 'BluetoothGattCharacteristic;[B)V')
    def onCharacteristicChanged(self, gatt, characteristic, value):
        data = bytes([b & 0xFF for b in value])
        status = 'failed sending'

        if len(data) >= 13 and data[9] == 0:
            status = 'was sent'

        logger.info(f"Notification {status} to device {self.DEVICE_NAME}")
        self.on_notify(data)


class BleSession:
    def __init__(self, address: str, DEVICE_NAME: str):
        self._connect_ok = False
        self._connect_status = None
        self._connected_evt = threading.Event()
        self._descriptor_evt = threading.Event()
        self._services_evt = threading.Event()
        self._write_evt = threading.Event()
        self.address = address
        self.DEVICE_NAME = DEVICE_NAME
        self.gatt = None
        self.listener = GattListener()
        self.listener.DEVICE_NAME = DEVICE_NAME
        self.listener.on_connected = self._on_connected
        self.listener.on_descriptor_write = self._on_descriptor_write
        self.listener.on_notify = self._on_notify
        self.listener.on_services_discovered = self._on_services_discovered
        self.listener.on_write = self._on_write
        self.callback = PyGattCallback(self.listener)

    def _on_connected(self, connected: bool, status: int):
        self._connect_ok = connected
        self._connect_status = status

        if connected:
            logger.info(f"Connected to {self.DEVICE_NAME}")
        else:
            logger.warning(f"Connection attempt ended, status={status}, "
                           "connected=False")

        self._connected_evt.set()

    def _on_services_discovered(self, ok: bool):
        self._services_evt.set()

    def _on_write(self, ok: bool):
        self._write_evt.set()

    def _on_descriptor_write(self, ok: bool):
        self._descriptor_evt.set()

    def _on_notify(self, data: bytes):
        pass

    def _connect_once(self, timeout: float):
        activity = PythonActivity.mActivity
        adapter = BluetoothAdapter.getDefaultAdapter()
        device = adapter.getRemoteDevice(self.address)
        logger.info(f"Connecting to {self.address}...")

        self._connected_evt.clear()
        self._services_evt.clear()
        self._connect_status = None
        self._connect_ok = False

        self.gatt = run_on_main_thread(
            lambda: device.connectGatt(activity, False, self.callback, 2),
            timeout=timeout,
        )

        if not self._connected_evt.wait(timeout):
            raise TimeoutError("Timed out connecting to device "
                               "(no callback at all)")
        if not self._connect_ok:
            raise ConnectionError("Connection failed, GATT status="
                                  f"{self._connect_status}")

        run_on_main_thread(self.gatt.discoverServices, timeout=timeout)
        if not self._services_evt.wait(timeout):
            raise TimeoutError("Timed out discovering services")

    def connect(self, timeout=10.0, retries=3, retry_delay=1.5):
        last_error = None
        for attempt in range(1, retries + 1):
            try:
                self._connect_once(timeout)
                return
            except (TimeoutError, ConnectionError) as exc:
                last_error = exc
                logger.warning(f"Connect attempt {attempt}/{retries} "
                               f"failed: {exc}")

                if self.gatt is not None:
                    try:
                        run_on_main_thread(self.gatt.close, timeout=5.0)
                    except Exception:
                        pass
                    self.gatt = None
                if attempt < retries:
                    time.sleep(retry_delay)
        raise last_error

    def enable_notify(self, char_uuid: str, timeout=5.0):
        service_char = self._find_characteristic(char_uuid)
        self.gatt.setCharacteristicNotification(service_char, True)
        descriptor = service_char.getDescriptor(UUID.fromString(CCCD_UUID))
        descriptor.setValue([0x01, 0x00])
        self._descriptor_evt.clear()

        ok = run_on_main_thread(
            lambda: self.gatt.writeDescriptor(descriptor), timeout=timeout
        )

        if not ok:
            raise RuntimeError("writeDescriptor() returned false -- GATT "
                               "busy or invalid state")

        if not self._descriptor_evt.wait(timeout):
            raise TimeoutError("Timed out enabling notifications "
                               "(descriptor write)")

    def disable_notify(self, char_uuid: str):
        service_char = self._find_characteristic(char_uuid)
        self.gatt.setCharacteristicNotification(service_char, False)

    def write(self, char_uuid: str, data: bytes, timeout=5.0):
        service_char = self._find_characteristic(char_uuid)
        service_char.setWriteType(WRITE_TYPE_NO_RESPONSE)
        service_char.setValue(_to_java_bytes(data))
        self._write_evt.clear()

        ok = run_on_main_thread(
            lambda: self.gatt.writeCharacteristic(service_char),
            timeout=timeout
        )

        if not ok:
            raise RuntimeError("writeCharacteristic() returned false -- GATT "
                               "busy or invalid state")

        self._write_evt.wait(timeout)

    def _find_characteristic(self, char_uuid: str):
        for service in self.gatt.getServices().toArray():
            char = service.getCharacteristic(UUID.fromString(char_uuid))
            if char is not None:
                return char
        raise ValueError(f"Characteristic {char_uuid} not found")

    def close(self):
        if self.gatt is not None:
            try:
                run_on_main_thread(self.gatt.close, timeout=5.0)
            except Exception:
                pass


class _BLENotification:
    async def send(self, message: str) -> None:
        async def is_ready(permissions, status):
            if all(status):
                loop = asyncio.get_running_loop()
                session = BleSession(self.DEVICE_ADDRESS, self.DEVICE_NAME)

                def _run():
                    session.connect()
                    session.enable_notify(self.NOTIFY_CHAR_UUID)
                    session.write(
                        self.WRITE_CHAR_UUID,
                        self.build_notification_message(message)
                    )

                try:
                    await loop.run_in_executor(None, _run)
                    await asyncio.sleep(.5)
                    await loop.run_in_executor(None, session.disable_notify,
                                               self.NOTIFY_CHAR_UUID)
                finally:
                    await loop.run_in_executor(None, session.close)

        await request_permissions(
            [
                Permission.BLUETOOTH_CONNECT,
                Permission.BLUETOOTH_SCAN,
                Permission.ACCESS_FINE_LOCATION,
            ],
            is_ready
        )
