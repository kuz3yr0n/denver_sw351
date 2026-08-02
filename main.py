import asyncio

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from src import BLENotification


class Base(BoxLayout):
    pass


class CloudDateToday(App):

    def build(self):
        self.ble_not = BLENotification(
            device_address="MAC-ADDRESS",
            device_name="SW-351",
            notify_char_uuid="long-string",
            write_char_uuid="long-string"
        )
        asyncio.ensure_future(self.ble_not.send("Hello World!"))
        return Base()


app = CloudDateToday()
asyncio.run(app.async_run())
# app.run()
