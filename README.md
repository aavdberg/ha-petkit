# Petkit BLE — Home Assistant Integration

[![Lint](https://github.com/aavdberg/ha-petkit/actions/workflows/lint.yml/badge.svg?branch=main)](https://github.com/aavdberg/ha-petkit/actions/workflows/lint.yml)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)

Local Bluetooth integration for **Petkit water fountains** (W4, W5, CTW3 series).  
Communicates directly over BLE — no cloud, no API token, no Petkit account required.

## Supported Devices

| Model     | BLE Name       | Notes                          |
|-----------|---------------|-------------------------------|
| CTW3      | Petkit_CTW3*  | Battery + AC, extra sensors   |
| CTW2      | Petkit_CTW2   |                               |
| W5C       | Petkit_W5C    |                               |
| W5N       | Petkit_W5N    |                               |
| W5        | Petkit_W5     |                               |
| W4X UVC   | Petkit_W4XUVC |                               |
| W4X       | Petkit_W4X    |                               |

## Features

- **Sensors**: filter life %, pump runtime, water purified, energy today, filter days remaining, battery (CTW3), RSSI
- **Binary sensors**: pump running, water missing, filter warning, hardware failure, DND, pet detected (CTW3), AC power (CTW3), low battery (CTW3)
- **Buttons**: reset filter, pump on, pump off
- **Switch**: power on/off
- **ESPHome Bluetooth proxy support** — works transparently via Home Assistant's native Bluetooth stack

## Requirements

- Home Assistant 2024.1 or newer
- A Bluetooth adapter or [ESPHome Bluetooth proxy](https://esphome.io/components/bluetooth_proxy.html)

## Installation via HACS

1. In HACS → **Integrations** → ⋮ → **Custom repositories**
2. Add `https://github.com/aavdberg/ha-petkit` with category **Integration**
3. Install **Petkit BLE** and restart Home Assistant

## Configuration

After installation, go to **Settings → Devices & Services → Add Integration → Petkit BLE**.

HA will scan for nearby Petkit fountains automatically. If none appear, enter the device's Bluetooth MAC address manually (found in the Petkit app or your router's ARP table).

The integration polls the fountain every 60 seconds. Commands (pump on/off, filter reset) connect on demand and refresh the state immediately after.

## Protocol Notes

Communication uses a proprietary BLE protocol over two GATT characteristics (notify + write-without-response). Authentication is required on every connection.

---

## Development

### Branching strategie

```
feature/* of fix/*
        │
        ▼  Pull Request + lint check
       dev         ← ontwikkeling & testen
        │
        ▼  Pull Request + lint check
      main         ← productie (HACS-gebruikers)
                      → automatisch GitHub Release
```

| Branch | Doel | Beschermd |
|---|---|---|
| `main` | Stabiele productie-release | ✅ PR verplicht + lint groen |
| `dev` | Integratie & testen | ✅ PR verplicht + lint groen |
| `feature/*` | Nieuwe functionaliteit | Vrij — PR naar `dev` |
| `fix/*` | Bugfixes | Vrij — PR naar `dev` |

### Bijdragen

1. Fork de repo of maak een branch op basis van `dev`:
   ```bash
   git checkout dev
   git checkout -b feature/mijn-functie
   ```
2. Maak je wijzigingen en commit:
   ```bash
   git commit -m "feat: beschrijving van de wijziging"
   ```
3. Push je branch en open een **Pull Request naar `dev`**:
   ```bash
   git push origin feature/mijn-functie
   ```
4. De lint-check (ruff) en Copilot code review lopen automatisch.
5. Wanneer `dev` stabiel is, wordt een PR naar `main` geopend voor de release.

### Releases

Bij elke merge naar `main` maakt de release-workflow automatisch een GitHub Release aan op basis van de `version` in `manifest.json`.  
Verhoog de versie in `manifest.json` op de `dev` branch vóór je een release PR maakt.

### Lokale ontwikkeling

```bash
# Afhankelijkheden installeren
pip install ruff

# Lint controleren
ruff check custom_components/

# Opmaak controleren
ruff format --check custom_components/

# Automatisch fixen
ruff check --fix custom_components/
```

