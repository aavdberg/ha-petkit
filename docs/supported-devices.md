# Supported Devices & Hardware Variants

The **ha-petkit** integration supports a wide range of Petkit smart water fountain models. Petkit uses internal hardware revision codes (such as `CTW3`, `CTW2`, `W5C`, `W4X`) in Bluetooth advertisement names.

---

## Marketing Name ↔ BLE Advertisement Name Mapping

| Marketing Product Name | BLE Advertisement Name | Power Source | Special Features |
|---|---|---|---|
| **Eversweet Max 2 (Cordless)** | `Petkit_CTW3_*` | Battery + AC Power | Extended 26-byte payload, battery level, pet detection, UV-C status |
| **Eversweet Solo 2** | `Petkit_CTW2_*` | AC Power | Wireless pump design, smart mode schedule |
| **Eversweet 3 Pro** | `Petkit_W5C_*` | AC Power | Standard 12-byte payload, flow rate divisor 1.0 |
| **Eversweet 3** | `Petkit_W5N_*` | AC Power | Standard 12-byte payload |
| **Eversweet (Original)** | `Petkit_W5_*` | AC Power | Standard 12-byte payload |
| **Eversweet W4X** | `Petkit_W4X_*` | AC Power | Standard 12-byte payload, flow rate divisor 1.8 |
| **Eversweet W4X UVC** | `Petkit_W4XUVC_*` | AC Power | UV-C sterilization hardware |

> **Note on Revision Codes:** "CTW" is Petkit's internal hardware platform code, independent of consumer generation numbers. For example, Eversweet Max 2 uses revision `CTW3`, while Eversweet Solo 2 uses revision `CTW2`.

---

## Feature Comparison Matrix

| Feature / Entity | CTW3 (Max 2) | CTW2 (Solo 2) | W5C / W5N / W5 | W4X / W4XUVC |
|---|---|---|---|---|
| **Filter Life %** | ✅ | ✅ | ✅ | ✅ |
| **Pump Runtime Today** | ✅ | ✅ | ✅ | ✅ |
| **Water Purified Today** | ✅ | ✅ | ✅ | ✅ |
| **Energy Consumed Today** | ✅ | ✅ | ✅ | ✅ |
| **Operating Mode Select** | ✅ | ✅ | ✅ | ✅ |
| **Reset Filter Button** | ✅ | ✅ | ✅ | ✅ |
| **Power Switch** | ✅ | ✅ | ✅ | ✅ |
| **Battery Level Sensor** | ✅ | ❌ | ❌ | ❌ |
| **Pet Detection Sensor** | ✅ | ❌ | ❌ | ❌ |
| **AC Power Sensor** | ✅ | ❌ | ❌ | ❌ |
| **Low Battery Warning** | ✅ | ❌ | ❌ | ❌ |
| **UVC Active Sensor** | ✅ | ❌ | ❌ | ❌ |
| **DND Schedule (Time)** | ❌ | ✅ | ✅ | ✅ |
| **LED Brightness Number** | ✅ (0-3) | ✅ (0-10) | ✅ (0-10) | ✅ (0-10) |
