# Denver SW-351 BLE Notification Protocol

**Status:** Unofficial, reverse-engineered, incomplete  
**Scope:** Sending a text notification from a BLE central (phone/computer) to a Denver SW-351 smartwatch  
**Source basis:** `kuz3yr0n/Denver_SW-351`, commit `611b30d`  
**Byte offsets:** Zero-based

## 1. Overview

The watch accepts notification text through a BLE GATT characteristic. The client:

1. Connects to the watch.
2. Discovers its GATT services and characteristics.
3. Subscribes to a notification characteristic.
4. Writes one encoded notification packet to a separate write characteristic, using **Write Without Response**.
5. Waits for a notification from the watch and interprets byte 9 as a status byte.

The repository does **not** publish the write or notification characteristic UUIDs. They must currently be obtained from a GATT service listing, for example with a BLE inspection application or by enumerating services with a BLE library. Once known, packet capture should not be necessary for sending text.

## 2. BLE/GATT requirements

| Item | Value |
|---|---|
| Advertised/device name used by the reference code | `SW-351` |
| Write characteristic | UUID not documented |
| Write method | Write Without Response |
| Response characteristic | UUID not documented; notifications enabled |
| CCCD UUID | `00002902-0000-1000-8000-00805f9b34fb` |
| CCCD value used to enable notifications | `01 00` |
| Delay used after writing | Approximately 500 ms |

The MAC address and both characteristic UUIDs are supplied by the caller in the reference implementation.

## 3. Notification packet

All multi-byte integer fields in the packet header are **big-endian**. Notification text is encoded as **UTF-16 little-endian**, without a byte-order mark and without an explicit null terminator.

### 3.1 Complete packet layout

| Offset | Size | Field | Value / meaning |
|---:|---:|---|---|
| 0 | 2 | Magic / command group | Constant `BA 20` |
| 2 | 2 | Inner length | Big-endian byte length of the complete inner message |
| 4 | 2 | Unknown field | Big-endian; reference implementation defaults to `00 00` |
| 6 | 2 | Constant | `00 0F` |
| 8 | Variable | Inner message | Described below |

The total packet size is:

```text
8 + inner_length
```

### 3.2 Inner-message layout

Offsets below are relative to the start of the inner message, which begins at complete-packet offset 8.

| Inner offset | Packet offset | Size | Field | Value / meaning |
|---:|---:|---:|---|---|
| 0 | 8 | 1 | Constant | `06` |
| 1 | 9 | 1 | Constant | `00` |
| 2 | 10 | 1 | Constant | `60` |
| 3 | 11 | 1 | Constant | `00` |
| 4 | 12 | 1 | Text-length field | Encoded text byte length plus 1 |
| 5 | 13 | 1 | Constant | `0A` |
| 6 | 14 | Variable | Text | UTF-16LE bytes |

For an encoded text payload of `P` bytes:

```text
inner_length       = 6 + P
text_length_field  = P + 1
total_packet_size  = 14 + P
```

The reference code stores `text_length_field` in one byte and masks it with `0xFF`. A conservative implementation should reject text whose UTF-16LE representation exceeds **254 bytes**, because larger values wrap in that field. This inferred limit has not been experimentally verified.

## 4. Worked example

Text:

```text
Hi
```

UTF-16LE payload:

```text
48 00 69 00
```

Payload length is 4 bytes, so:

```text
inner_length      = 6 + 4 = 10 = 00 0A
text-length field = 4 + 1 = 5  = 05
```

Complete packet:

```text
BA 20 00 0A 00 00 00 0F 06 00 60 00 05 0A 48 00 69 00
```

Annotated:

```text
BA 20       magic
00 0A       inner-message length: 10 bytes
00 00       unknown field
00 0F       constant
06 00 60 00 inner-message constants
05          encoded text length + 1
0A          constant
48 00 69 00 "Hi" in UTF-16LE
```

## 5. Packet construction

Language-neutral algorithm:

```text
payload = UTF16_LE(text)

require length(payload) <= 254

inner =
    06 00 60 00
    || BYTE(length(payload) + 1)
    || 0A
    || payload

packet =
    BA 20
    || UINT16_BE(length(inner))
    || UINT16_BE(unknown_field)
    || 00 0F
    || inner
```

Equivalent Python:

```python
def build_notification(text: str, unknown_field: int = 0) -> bytes:
    payload = text.encode("utf-16-le")

    if len(payload) > 254:
        raise ValueError("Notification text is too long for the observed format")

    inner = (
        b"\x06\x00\x60\x00"
        + bytes([len(payload) + 1])
        + b"\x0a"
        + payload
    )

    return (
        b"\xba\x20"
        + len(inner).to_bytes(2, "big")
        + unknown_field.to_bytes(2, "big")
        + b"\x00\x0f"
        + inner
    )
```

## 6. Exchange sequence

```text
Central                                      SW-351
   |                                            |
   |--- Connect BLE GATT ---------------------->|
   |--- Discover services/characteristics ----->|
   |--- Enable notify characteristic ---------->|
   |    CCCD = 01 00                            |
   |--- Write packet, without response -------->|
   |<-- Notification / acknowledgement --------|
   |--- Disable notifications ----------------->|
   |--- Disconnect ---------------------------->|
```

The reference implementation waits approximately 500 ms after the write to receive the acknowledgement.

## 7. Acknowledgement

The complete acknowledgement structure is unknown.

The reference implementation treats an incoming notification as successful when:

```text
response length >= 13
and
response[9] == 00
```

Any other received value is logged as a failure.

This should be treated as an observed status heuristic, not a fully decoded response format. Implementations should retain/log the complete response bytes so that additional fields can be documented later.

## 8. Known unknowns

The following information is not established by the repository:

- GATT service UUID.
- Write characteristic UUID.
- Notification characteristic UUID.
- Meaning of packet bytes 4–5 (`unknown_field`).
- Semantic meaning of constants `00 0F`, `06 00 60 00`, and `0A`.
- Complete acknowledgement layout and error-code values.
- Whether long packets can be fragmented, or whether the connection must negotiate a sufficiently large ATT MTU.
- Whether notification categories, sender/application names, titles, multiline content, or message identifiers are supported.
- Whether the inferred 254-byte payload limit matches the watch firmware's actual limit.
- Whether this format works on firmware revisions other than the one tested by the repository author.

## 9. Interoperability recommendations

An implementation should:

1. Enumerate and record the watch's GATT service and characteristic UUIDs.
2. Verify that the selected write characteristic supports Write Without Response.
3. Subscribe to the response characteristic before writing.
4. Validate packet lengths rather than allowing the one-byte text-length field to wrap.
5. Log raw acknowledgements and firmware/device information.
6. Avoid assigning meanings to unknown constants until they have been tested by varying one field at a time.
7. Test non-ASCII text, emoji, maximum lengths, multiline text, reconnection, and repeated notifications.

## 10. Confidence summary

| Part | Confidence |
|---|---|
| Packet construction shown above | High: directly implemented in the repository |
| UTF-16LE text encoding | High |
| Big-endian outer integer fields | High |
| BLE write-without-response flow | High |
| Success check at response byte 9 | Medium: directly used, but response format is otherwise unknown |
| 254-byte conservative maximum | Medium: inferred from the one-byte field |
| Meanings assigned to constant/unknown fields | Unknown |
| UUIDs | Not supplied |
