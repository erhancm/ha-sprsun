"""Register map loading and FC3 block packing for SPRSUN CG248075."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .const import GROUP_ORDER, RAW_ONLY, SCALE_OVERRIDES

DATA_DIR = Path(__file__).resolve().parent / "data"


@dataclass(frozen=True)
class RegisterDef:
    addr: int
    addr_hex: str
    name: str
    group: str
    rw: bool
    scale: float | None
    unit: str | None
    device_class: str | None

    def effective_scale(self) -> float | None:
        if self.addr in RAW_ONLY:
            return None
        if self.addr in SCALE_OVERRIDES:
            return SCALE_OVERRIDES[self.addr]
        return self.scale


def load_registers() -> list[RegisterDef]:
    path = DATA_DIR / "CG248075-V1.2-registers.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [
        RegisterDef(
            addr=int(r["addr"]),
            addr_hex=r.get("addr_hex", hex(int(r["addr"]))),
            name=r["name"],
            group=r["group"],
            rw=bool(r.get("rw")),
            scale=r.get("scale"),
            unit=r.get("unit"),
            device_class=r.get("device_class"),
        )
        for r in raw
    ]


def load_bitfields() -> list[dict[str, Any]]:
    path = DATA_DIR / "CG248075-V1.2-bitfields.json"
    return json.loads(path.read_text(encoding="utf-8"))


def registers_for_limit(regs: list[RegisterDef], limit: int) -> list[RegisterDef]:
    rank = {g: i for i, g in enumerate(GROUP_ORDER)}
    ordered = sorted(regs, key=lambda r: (rank.get(r.group, 999), r.addr))
    if limit >= len(ordered):
        return ordered
    return ordered[:limit]


def pack_blocks(addresses: list[int], max_block: int = 125) -> list[tuple[int, int]]:
    addrs = sorted(set(addresses))
    if not addrs:
        return []
    blocks: list[tuple[int, int]] = []
    i = 0
    n = len(addrs)
    while i < n:
        start = addrs[i]
        limit = start + max_block
        j = i
        while j < n and addrs[j] < limit:
            j += 1
        last = addrs[j - 1]
        blocks.append((start, last - start + 1))
        i = j
    return blocks


def to_signed16(raw: int) -> int:
    return raw - 0x10000 if raw >= 0x8000 else raw


def decode_value(reg: RegisterDef, raw: int) -> float | int:
    signed = to_signed16(raw)
    scale = reg.effective_scale()
    if scale is None or scale == 1.0:
        return signed
    return round(signed * scale, 1)


def setpoint_c(raw: int) -> float:
    return (raw & 0xFF) * 0.5


def pack_setpoint_c(celsius: float, existing: int = 0) -> int:
    """Write lower 8 bits as °C/0.5; preserve upper bits from existing raw."""
    n = int(round(celsius / 0.5)) & 0xFF
    return (existing & 0xFF00) | n


def slug(text: str) -> str:
    out = []
    for ch in text.lower():
        if ch.isalnum():
            out.append(ch)
        else:
            out.append("_")
    x = "".join(out)
    while "__" in x:
        x = x.replace("__", "_")
    return x.strip("_")[:48]
