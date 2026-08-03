import asyncio
import threading

try:
    from jnius import PythonJavaClass, autoclass, java_method
except ImportError:

    def autoclass(_):
        raise RuntimeError("pyjnius not available")


from android.config import ACTIVITY_CLASS_NAME, ACTIVITY_CLASS_NAMESPACE

PERMISSION_GRANTED = 0
PERMISSION_DENIED = -1


class _onRequestPermissionsCallback(PythonJavaClass):
    __javainterfaces__ = [ACTIVITY_CLASS_NAMESPACE + "$PermissionsCallback"]
    __javacontext__ = "app"

    def __init__(self, func, loop):
        self.func = func
        self.loop = loop
        super().__init__()

    @java_method("(I[Ljava/lang/String;[I)V")
    def onRequestPermissionsResult(
        self, requestCode, permissions, grantResults
    ):
        asyncio.run_coroutine_threadsafe(
            self.func(requestCode, permissions, grantResults), self.loop
        )


class _RequestPermissionsManager:
    _SDK_INT = None
    _java_callback = None
    _callbacks = {}
    _callback_id = 1
    _lock = threading.Lock()

    @classmethod
    def register_callback(cls, loop):
        cls._java_callback = _onRequestPermissionsCallback(
            cls.python_callback, loop
        )
        mActivity = autoclass(ACTIVITY_CLASS_NAME).mActivity
        mActivity.addPermissionsCallback(cls._java_callback)

    @classmethod
    async def request_permissions(cls, permissions, callback=None):
        loop = asyncio.get_running_loop()
        if not cls._SDK_INT:
            VERSION = autoclass("android.os.Build$VERSION")
            cls._SDK_INT = VERSION.SDK_INT
        if cls._SDK_INT < 23:
            if callback:
                res = [True for _ in permissions]
                if asyncio.iscoroutinefunction(callback):
                    await callback(permissions, res)
                else:
                    callback(permissions, res)
            return

        with cls._lock:
            if not cls._java_callback:
                cls.register_callback(loop)
            mActivity = autoclass(ACTIVITY_CLASS_NAME).mActivity
            if not callback:
                mActivity.requestPermissions(permissions)
            else:
                cls._callback_id += 1
                cls._callbacks[cls._callback_id] = callback
                mActivity.requestPermissionsWithRequestCode(
                    permissions, cls._callback_id
                )

    @classmethod
    async def python_callback(cls, requestCode, permissions, grantResults):
        grant_results = [x == PERMISSION_GRANTED for x in grantResults]
        cb = cls._callbacks.pop(requestCode, None)
        if cb:
            if asyncio.iscoroutinefunction(cb):
                await cb(permissions, grant_results)
            else:
                cb(permissions, grant_results)


async def request_permissions(permissions, callback=None):
    await _RequestPermissionsManager.request_permissions(
        permissions, callback
    )
