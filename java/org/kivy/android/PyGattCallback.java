package org.kivy.android;

import android.bluetooth.BluetoothGatt;
import android.bluetooth.BluetoothGattCallback;
import android.bluetooth.BluetoothGattCharacteristic;
import android.bluetooth.BluetoothGattDescriptor;


public class PyGattCallback extends BluetoothGattCallback {

    public interface PyGattListener {
        void onConnectionStateChange(BluetoothGatt gatt, int status, int newState);
        void onServicesDiscovered(BluetoothGatt gatt, int status);
        void onCharacteristicWrite(BluetoothGatt gatt, BluetoothGattCharacteristic characteristic, int status);
        void onDescriptorWrite(BluetoothGatt gatt, BluetoothGattDescriptor descriptor, int status);
        void onCharacteristicChanged(BluetoothGatt gatt, BluetoothGattCharacteristic characteristic, byte[] value);
    }

    private final PyGattListener listener;

    public PyGattCallback(PyGattListener listener) {
        this.listener = listener;
    }

    @Override
    public void onConnectionStateChange(BluetoothGatt gatt, int status, int newState) {
        listener.onConnectionStateChange(gatt, status, newState);
    }

    @Override
    public void onServicesDiscovered(BluetoothGatt gatt, int status) {
        listener.onServicesDiscovered(gatt, status);
    }

    @Override
    public void onCharacteristicWrite(BluetoothGatt gatt, BluetoothGattCharacteristic characteristic, int status) {
        listener.onCharacteristicWrite(gatt, characteristic, status);
    }

    @Override
    public void onDescriptorWrite(BluetoothGatt gatt, BluetoothGattDescriptor descriptor, int status) {
        listener.onDescriptorWrite(gatt, descriptor, status);
    }

    // For API 33+
    @Override
    public void onCharacteristicChanged(
        BluetoothGatt gatt, 
        BluetoothGattCharacteristic characteristic, 
        byte[] value
    ) {
        listener.onCharacteristicChanged(gatt, characteristic, value);
    }

    // For API 32 and lower
    @SuppressWarnings("deprecation")
    @Override
    public void onCharacteristicChanged(
        BluetoothGatt gatt, 
        BluetoothGattCharacteristic characteristic
    ) {
        listener.onCharacteristicChanged(
            gatt, 
            characteristic, 
            characteristic.getValue()
        );
    }
}
