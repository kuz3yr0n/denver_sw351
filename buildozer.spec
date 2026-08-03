[app]
title = SW-351 BT Test
package.name = blutooth
package.domain = org.kuzeyron
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.2
requirements = python3,kivy
fullscreen = 0
android.permissions = BLUETOOTH_CONNECT,BLUETOOTH_SCAN,ACCESS_FINE_LOCATION
android.add_src = java
android.logcat_filters = *:S python:D
android.archs = arm64-v8a

[buildozer]
log_level = 2
warn_on_root = 1
