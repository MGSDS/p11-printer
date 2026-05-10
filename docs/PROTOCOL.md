# P11-GZP Protocol Reference

Disclaimer: documentrarion adaptation done by AI

Based on the [Fichero D11s protocol](https://github.com/0xMH/fichero-printer/blob/main/docs/PROTOCOL.md) reverse-engineered by [@0xMH](https://github.com/0xMH). The P11-GZP uses the same AiYin/LuckPrinter SDK internals with the differences noted below.

## P11 vs D11s differences

| | D11s | P11-GZP |
|---|---|---|
| BLE service used | `18f0` (`2af1`/`2af0`) | `ff00` (`ff02`/`ff01`) |
| `set_paper_type` ACK | Returns `OK` | No response |
| Classic BT | Yes (SPP) | Yes (SPP, Android only) |
| BLE name prefix | `FICHERO_`, `D11s_` | `P11_` |
| Confirmed firmware | 2.4.6 | 6013 |

All other commands below are shared with the D11s and verified on P11-GZP firmware 6013.

## Hardware

- Printhead: 96 pixels wide (12 bytes/row)
- DPI: 203 (8 dots/mm)
- Connection: BLE (macOS/Linux/Windows)
- BT name: `P11_XXXX`

## BLE Services

All four services exist on P11 and respond to ESC/POS probes. Use `ff00`:

| Service UUID | Write Char | Notify Char |
|---|---|---|
| `000018f0` | `2af1` | `2af0` |
| `0000ff00` ✓ | `ff02` | `ff01` |
| `e7810a71...` | `bef8d6c9...` | `bef8d6c9...` |
| `49535343...` | `4953...9bb3` | `4953...9616` |

## Info Commands

| Bytes | Command | Response | P11 Example |
|---|---|---|---|
| `10 FF 20 F0` | Get model | ASCII | `P11-GZP` |
| `10 FF 20 F1` | Get firmware | ASCII | `6013` |
| `10 FF 20 F2` | Get serial | ASCII | `268519826` |
| `10 FF 20 EF` | Get boot version | ASCII | `GZP202` |
| `10 FF 50 F1` | Get battery | 2 bytes `[status, %]` | `00 32` = 50% |
| `10 FF 40` | Get status | 1 byte bitmask | `00` = ready |
| `10 FF 11` | Get density | 3 bytes | |
| `10 FF 13` | Get shutdown time | 2 bytes big-endian (min) | `00 0A` = 10 min |
| `10 FF 70` | Get all info | pipe-delimited ASCII | see below |

## Status Byte Bitmask (`10 FF 40` response)

| Bit | Mask | Meaning |
|-----|------|---------|
| 0 | `0x01` | Currently printing |
| 1 | `0x02` | Cover open |
| 2 | `0x04` | Out of paper |
| 3 | `0x08` | Low battery |
| 4 | `0x10` | Overheated |
| 5 | `0x20` | Charging |
| 6 | `0x40` | Overheated (alt) |

## All-Info Response (`10 FF 70`)

Pipe-delimited: `BT_NAME|MAC_CLASSIC|MAC_BLE|FIRMWARE|SERIAL|BATTERY`

## Config Commands

| Bytes | Command | Parameters | Response |
|---|---|---|---|
| `10 FF 10 00 nn` | Set density | 0=light 1=medium 2=thick | `OK` |
| `10 FF 84 nn` | Set paper type | 0=gap 1=black mark 2=continuous | *(none on P11)* |
| `10 FF 12 HH LL` | Set shutdown time | big-endian minutes | `OK` |
| `10 FF 04` | Factory reset | | `OK` |

## Print Sequence

```
1. 10 FF 10 00 nn          Set density
2. 10 FF 84 00             Set paper type = gap/label (P11: no ACK)
3. 00 × 12                 Wakeup
4. 10 FF FE 01             Enable printer (AiYin-specific)
5. 1D 76 30 00 0C 00 yL yH  Raster image (GS v 0)
   [pixel data...]
6. 1D 0C                   Form feed → next label
7. 10 FF FE 45             Stop print → wait for "OK" (60s timeout)
```

## Raster Image Format (`GS v 0`)

```
1D 76 30 mm xL xH yL yH [data]
```

| Field | Value for P11 |
|---|---|
| `mm` | `00` (normal) |
| `xL xH` | `0C 00` (12 bytes = 96px wide) |
| `yL yH` | `F0 00` (240 rows = 30mm) |

Data: 1 bit per pixel, MSB = leftmost. 1=black, 0=white. Total = `xL × yL` bytes.

**Note:** ESC * (bit-image line mode) does NOT work over BLE on the P11. GS v 0 only.

## Feed Commands

| Bytes | Command |
|---|---|
| `1D 0C` | Form feed — advance to next label |
| `1B 4A nn` | Feed forward nn dots |
