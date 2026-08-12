# Register documents

These files are the Modbus reference shipped with this integration.

| File | What it is |
|------|------------|
| [RS485-CG248075-MODBUS-V1.2-EN-2022.07.05.pdf](RS485-CG248075-MODBUS-V1.2-EN-2022.07.05.pdf) | Vendor protocol PDF (**authoritative**) |
| [CG248075-V1.2-extract.txt](CG248075-V1.2-extract.txt) | Plain-text extract of that PDF |
| [CG248075-V1.2-registers.json](CG248075-V1.2-registers.json) | Parsed holding-register list used by the integration |
| [CG248075-V1.2-bitfields.json](CG248075-V1.2-bitfields.json) | Bit masks for status / output / failure words |
| [key-registers.md](key-registers.md) | Short curated table (power, mode, setpoints, temps) |

Serial defaults in the PDF / live hardware: **19200-8-N-2**, slave **1**, function codes **03 / 06 / 10**.

> Older community “Carel / DC inverter APP” spreadsheets (status `@217`, temps `@188–196`, coil `40`) do **not** match this map. Do not mix them.

The `CG248075` string in the filenames is the vendor’s protocol document code
(July 2022 V1.2). It is not a heat-pump model name.
