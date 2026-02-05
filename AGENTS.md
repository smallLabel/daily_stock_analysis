# AGENTS.md - Development Guidelines for AI Agents

This document provides guidelines for AI coding agents working on this stock analysis system.

## Build, Lint, and Test Commands

### Installation
```bash
pip install -r requirements.txt
pip install flake8 black isort bandit pytest
```

### Linting (Required Before Commit)
```bash
# Check syntax errors (blocking)
python -m py_compile main.py src/*.py data_provider/*.py

# Static analysis for critical errors (E9, F63, F7, F82)
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics

# Format code with Black (line-length: 120)
black src/ tests/ main.py --line-length 120

# Sort imports automatically
isort src/ tests/ data_provider/ --profile black --line-length 120

# Bandit security check (skip test assertions)
bandit -r src/ --exclude-dir=tests
```

### Running Tests
```bash
# Run all tests
pytest -v --tb=short

# Run single test file
pytest tests/test_imports.py -v --tb=short

# Run single test function
pytest tests/test_imports.py::test_specific_function -v --tb=short

# Import verification (manual)
python test_imports.py
```

### Docker
```bash
# Build and verify
docker build -t stock-analysis:test -f docker/Dockerfile .
docker run --rm stock-analysis:test python -c "print('OK')"
```

## Code Style Guidelines

### General Principles
- Write in **English** for code identifiers (variables, functions, classes)
- Use **Chinese** for comments and docstrings when explaining domain concepts
- Maximum line length: **120 characters**
- Python 3.10+ required

### Imports
- Standard library first, then third-party, then local
- Use absolute imports: `from src.config import Config`
- Separate import groups with blank lines
- Sort within groups using isort with Black profile

```python
# Standard library
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

# Third-party
import pandas as pd
from dotenv import load_dotenv
from tenacity import retry, wait_exponential

# Local
from src.config import get_config
from src.enums import ReportType
```

### Types
- Use type hints for function parameters and return values
- Prefer `typing.Dict`, `typing.List`, `typing.Optional` over `dict`, `list`
- Use dataclasses for structured data (config, models, DTOs)
- Use StrEnum for string-based enums

```python
from dataclasses import dataclass
from typing import Optional
from enum import Enum

class ReportType(str, Enum):
    SIMPLE = "simple"
    FULL = "full"

@dataclass
class StockConfig:
    symbol: str
    name: Optional[str] = None
    threshold: float = 5.0
```

### Naming Conventions
- **Classes**: PascalCase (`StockAnalyzer`, `NotificationService`)
- **Functions/Variables**: snake_case (`get_config`, `stock_list`)
- **Constants**: UPPER_SNAKE_CASE (`MAX_RETRIES`, `API_DELAY`)
- **Private members**: Leading underscore (`_private_method`, `_cache`)

### Error Handling
- Use `try/except` with specific exception types
- Log errors with `logger.error()` (not print)
- Propagate exceptions for caller to handle
- Use tenacity for API retries with exponential backoff

```python
from tenacity import retry, wait_exponential, stop_after_attempt

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2))
def fetch_data(self, symbol: str) -> Dict:
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch {symbol}: {e}")
        raise
```

### Logging
- Use `logger = logging.getLogger(__name__)`
- Log levels: DEBUG (details), INFO (progress), WARNING (issues), ERROR (failures)
- Never commit code with `print()` statements (use logging instead)

### File Headers
Include encoding and module docstring:

```python
# -*- coding: utf-8 -*-
"""
===================================
Module Name - Brief Description
===================================

Responsibilities:
1. First responsibility
2. Second responsibility
"""

import os
from typing import Any
```

### Module Structure
- Keep modules focused (single responsibility)
- Group related functions into classes
- Use `__init__.py` for package exports
- Maximum ~500 lines per file; split if larger

### Configuration
- Use environment variables for all secrets (`.env` file)
- Use dataclasses with `field(default_factory=list)` for list configs
- Provide sensible defaults for optional settings

### Notifications
- Support multiple channels (WeChat, Feishu, Telegram, Email, Discord)
- Use Webhooks for async notifications
- Return structured results for UI display
