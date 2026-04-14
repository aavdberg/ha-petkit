# Config Flow Guide

## Overview

Config flows handle user setup and device discovery. They run in `config_flow.py` and
inherit from `ConfigFlow`.

```python
from __future__ import annotations

from homeassistant.config_entries import ConfigFlow
from .const import DOMAIN

class MyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for My Integration."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle a user-initiated config flow."""
        ...
```

## Unique ID

**Always set a unique ID** before creating a config entry:

```python
await self.async_set_unique_id(formatted_address)
self._abort_if_unique_id_configured()
```

This prevents duplicate entries for the same device.

## Bluetooth Discovery

For BLE integrations, implement `async_step_bluetooth()`:

```python
async def async_step_bluetooth(
    self, discovery_info: BluetoothServiceInfoBleak
) -> ConfigFlowResult:
    """Handle bluetooth discovery."""
    await self.async_set_unique_id(
        dr.format_mac(discovery_info.address)
    )
    self._abort_if_unique_id_configured()

    self._discovery_info = discovery_info
    return self.async_show_form(
        step_id="bluetooth_confirm",
        description_placeholders={"name": discovery_info.name},
    )
```

## User Step

For manual configuration:

```python
async def async_step_user(self, user_input=None):
    """Handle a manual config entry."""
    errors = {}
    if user_input is not None:
        address = user_input[CONF_ADDRESS]
        await self.async_set_unique_id(dr.format_mac(address))
        self._abort_if_unique_id_configured()

        # Validate connection if needed
        try:
            await self._validate_device(address)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        else:
            return self.async_create_entry(
                title=user_input.get(CONF_NAME, "Device"),
                data=user_input,
            )

    return self.async_show_form(
        step_id="user",
        data_schema=vol.Schema({
            vol.Required(CONF_ADDRESS): str,
            vol.Optional(CONF_NAME): str,
        }),
        errors=errors,
    )
```

## Secrets

**Never store secrets in source code.** Use config entry data:

```python
return self.async_create_entry(
    title="My Device",
    data={
        CONF_ADDRESS: address,
        CONF_SECRET: secret.hex(),  # Store as hex string
    },
)
```

Retrieve in coordinator/client:
```python
secret_hex = entry.data.get(CONF_SECRET, "")
secret = bytes.fromhex(secret_hex) if secret_hex else None
```

Always wrap `bytes.fromhex()` in try/except for corrupted data resilience.

## Options Flow

For runtime configuration changes:

```python
class MyOptionsFlow(OptionsFlow):
    """Options flow for My Integration."""

    async def async_step_init(self, user_input=None):
        """Handle options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(CONF_SCAN_INTERVAL, 60),
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=600)),
            }),
        )
```

Register it in the config flow class:
```python
@staticmethod
@callback
def async_get_options_flow(config_entry):
    return MyOptionsFlow()
```

## Abort Reasons

Common abort reasons (define in strings.json):
- `already_configured` — Device already set up
- `already_in_progress` — Another flow for this device is active
- `no_devices_found` — Scan found no compatible devices
- `cannot_connect` — Connection to device failed
