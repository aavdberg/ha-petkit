# Code Quality Guide

## Type Hints

Every function must have type annotations:

```python
from __future__ import annotations

from collections.abc import Callable

def calculate_filter_days(
    filter_pct: int,
    mode: int,
    on_time: float,
    off_time: float,
) -> int:
    """Calculate remaining filter days."""
    ...
```

## Imports

Correct import sources (Python 3.12+):

```python
# ✅ Correct
from collections.abc import Callable, Coroutine, Mapping, Sequence
from typing import Any, TypeVar

# ❌ Wrong (ruff UP035)
from typing import Callable, Dict, List, Optional, Tuple
```

Use `X | None` instead of `Optional[X]`:

```python
# ✅ Correct
def get_value(data: MyData) -> float | None:

# ❌ Wrong
def get_value(data: MyData) -> Optional[float]:
```

## Ruff

Ruff is the standard linter. Run before every commit:

```bash
ruff check custom_components/
ruff format --check custom_components/
```

Auto-fix formatting:
```bash
ruff format custom_components/
```

Key ruff rules:
- `UP035`: Use `collections.abc` for `Callable`, etc.
- `UP007`: Use `X | Y` union syntax
- Line length: typically 88-120 chars (configured in `pyproject.toml`)

## Struct Packing

Use unsigned format for device IDs:

```python
# ✅ Correct — unsigned, handles full 64-bit range
struct.pack(">Q", device_id)

# ❌ Wrong — signed, raises error for IDs with high bit set
struct.pack(">q", device_id)
```

## Logging

Use `_LOGGER` with appropriate levels:

```python
_LOGGER = logging.getLogger(__name__)

# Debug: protocol details, raw data
_LOGGER.debug("Received frame: cmd=%d data=%s", cmd, data.hex())

# Info: significant state changes
_LOGGER.info("Device authenticated successfully")

# Warning: recoverable issues
_LOGGER.warning("Invalid stored secret, re-initializing")

# Error: unrecoverable issues (usually followed by UpdateFailed)
_LOGGER.error("Failed to connect after 3 retries")
```

## Testing

Test structure:
```
tests/
├── __init__.py
├── conftest.py        # Shared fixtures
├── test_protocol.py   # Protocol encode/decode tests
├── test_data_model.py # Data model property tests
└── test_config_flow.py # Config flow tests (if applicable)
```

Run tests:
```bash
python -m pytest tests/ -v
```

Use `pytest` with `unittest.mock` for mocking HA components:

```python
from unittest.mock import AsyncMock, patch

async def test_coordinator_update():
    """Test coordinator fetches data."""
    client = AsyncMock()
    client.async_get_data.return_value = MyDataClass(...)
    coordinator = MyCoordinator(hass, client)
    await coordinator.async_refresh()
    assert coordinator.data.temperature == 25.0
```

## Conventional Commits

```
feat: add LED brightness control
fix: correct filter days calculation for smart mode
docs: update README with CTW3 setup instructions
refactor: extract payload builders to protocol.py
ci: add ruff format check to lint workflow
chore: bump manifest version to 1.3.0
```
