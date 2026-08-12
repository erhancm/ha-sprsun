# Key registers

Authoritative map: vendor PDF
[RS485-CG248075-MODBUS-V1.2-EN-2022.07.05.pdf](RS485-CG248075-MODBUS-V1.2-EN-2022.07.05.pdf)
(July 2022).

Live-confirmed on a **CGK030-V3L-B** via EW11 Modbus TCP (slave 1) — including
power on/off write/readback and compressor spin-up.

Serial: **19200-8-N-2**. Function codes **03 / 06 / 10**.  
Addresses below are zero-based holding-register indexes (what goes on the wire).

## Control (holding, read/write)

| Address | Name | Encoding | Notes |
|---|---|---|---|
| 50 (`0x0032`) | Param marker / power | bit 0: `0` OFF · `1` ON | **Live-confirmed.** Other bits are flags — always read-modify-write; never write bare `0`/`1`. |
| 54 (`0x0036`) | P06 Unit mode | int 0–4 | `0` DHW · `1` Heating · `2` Cooling · `3` Heating+DHW · `4` Cooling+DHW |
| 202 (`0x00CA`) | P04 Hot water setpoint | lower 8 bits × 0.5 °C | Range 10–55 °C |
| 203 (`0x00CB`) | P02 Cooling setpoint | lower 8 bits × 0.5 °C | Range 12–30 °C |
| 204 (`0x00CC`) | P01 Heating setpoint | lower 8 bits × 0.5 °C | Range 10–55 °C |

## Temperatures (holding, read-only)

| Address | Name | Scale |
|---|---|---|
| 14 (`0x000E`) | Inlet water | ×0.1 °C |
| 15 (`0x000F`) | Hot water tank | ×0.1 °C |
| 17 (`0x0011`) | Ambient | ×0.5 °C |
| 18 (`0x0012`) | Outlet water | ×0.1 °C |
| 21 (`0x0015`) | Suction gas | ×0.5 °C |
| 22 (`0x0016`) | Coil | ×0.5 °C |
| 27 (`0x001B`) | Exhaust gas | ×1 °C |

## Machine status (holding, read-only)

| Address | Name |
|---|---|
| 28 (`0x001C`) | EEV1 steps |
| 30 (`0x001E`) | Compressor frequency (Hz) |
| 33 (`0x0021`) | DC bus voltage (V) |
| 35 (`0x0023`) | Compressor current (A) |
| 36 (`0x0024`) | Target frequency (Hz) |
| 38 (`0x0026`) | DC fan 1 speed |

## Bitfield status words

| Address | Name | Useful bits |
|---|---|---|
| 2 (`0x0002`) | Switching inputs | bit4 flow switch |
| 3 (`0x0003`) | Working status | bit0 DHW · bit1 heat · bit5 cool · bit6 alarm · bit7 defrost |
| 4 (`0x0004`) | Output 1 | bit0 compressor · bit5 fan · bit6 4-way · bit7 fan high |
| 5 (`0x0005`) | Output 2 | bit0 chassis heater · bit6 3-way · bit7 DHW heater |
| 6 (`0x0006`) | Output 3 | bit0 A/C pump · bit1 crank heater · bit6 pump |
| 7–13 | Failure symbols 1–7 | any non-zero ⇒ fault present |

## Do not use (wrong map)

Older Carel / “DC inverter APP” sheets (status `@217`, temps `@188–196`, coil `40`,
setpoints `@1–3`) **do not match** this firmware. Keep them for historical
reference only.
