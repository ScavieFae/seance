# Séance — Room Schematic

## Full Venue Layout

```
                    ┌─── CONFERENCE ROOM ──────────────────────┐
                    │                                          │
                    │  [Green 05]   [Violet 10]   [Gold 03]    │  ← back row
                    │                              ⬡ Board D   │
                    │  [Lime 04]    [Orange 02]   [Red 01]     │  ← middle row
                    │   ⬡ Board                                │
                    │  [Crimson 12] [Blue 08]   [Hot Pink 11]  │  ← front row
                    │                                          │
                    └──────────────┬──────┬────────────────────┘
                                  │ DOOR │
                                  └──┬───┘
                                     │
                                [Peach 13]
                                     │
    ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ MAIN VENUE ─ ─
                                     │
                    ╔════════════════════════════════════╗
    outer edge →    ║  [Indigo 09]           [White 07]  ║
                    ║      ⬡ Board A    ⬡ Board B       ║  ← OUR TABLE
                    ║        (laptops face away from room) ║
                    ╚════════════════════════════════════╝
```

**Orientation:** We sit at the table facing away from the conference room. Candles are on the outer edge of the table (further from the room). Boards A and B are between us and the conference room.

## Candle Reference

| Candle | Color | Hex | Location |
|--------|-------|-----|----------|
| 01 | Red | #FF0000 | Conf room — middle right |
| 02 | Orange | #FF5000 | Conf room — middle center |
| 03 | Gold | #FFC800 | Conf room — back right |
| 04 | Lime | #B4FF00 | Conf room — middle left |
| 05 | Green | #00FF00 | Conf room — back left |
| 06 | Mint | #00FFB4 | OFFLINE |
| 07 | White | #FFFFFF | Our table — outer edge right |
| 08 | Blue | #0000FF | Conf room — front center |
| 09 | Indigo | #5000FF | Our table — outer edge left |
| 10 | Violet | #C800FF | Conf room — back center |
| 11 | Hot Pink | #FF0096 | Conf room — front right |
| 12 | Crimson | #FF0032 | Conf room — front left |
| 13 | Peach | #FF9632 | Outside conf room door |

## Sensors

| Board | IP | Location |
|-------|-----|----------|
| A | 10.9.0.237 | Our table — connected to laptop |
| B | 10.9.0.199 | Our table — connected to laptop |
| C | 10.9.0.110 | Conference room — near Lime (04) |
| D | 10.9.0.242 | Conference room — near Gold (03) |

Two boards in conference room give cross-coverage of that space. Two boards at our table cover the main venue transition zone.
