# Python Testing Guide for portunix-ireco

## Overview

Testing frameworks and strategies for Python development in portunix-ireco.

## Testing Frameworks

### pytest (Recommended)

```python
import pytest
from portunix-ireco.calculator import Calculator

def test_addition():
    calc = Calculator()
    assert calc.add(2, 3) == 5

@pytest.mark.parametrize("a,b,expected", [
    (1, 2, 3),
    (0, 0, 0),
    (-1, 1, 0),
])
def test_add_parametrized(a, b, expected):
    calc = Calculator()
    assert calc.add(a, b) == expected

def test_division_by_zero():
    calc = Calculator()
    with pytest.raises(ZeroDivisionError):
        calc.divide(10, 0)
```

### unittest (Built-in)

```python
import unittest
from unittest.mock import Mock, patch

class TestCalculator(unittest.TestCase):
    def setUp(self):
        self.calc = Calculator()
    
    def test_addition(self):
        result = self.calc.add(2, 3)
        self.assertEqual(result, 5)
    
    @patch('portunix-ireco.service.external_api_call')
    def test_with_mock(self, mock_api):
        mock_api.return_value = {'status': 'success'}
        result = self.service.process_data()
        self.assertTrue(result)
```

## Test Organization

### Directory Structure

```text
tests/
├── unit/
├── integration/
├── fixtures/
├── conftest.py
└── __init__.py
```

### Fixtures

```python
# conftest.py
import pytest
from portunix-ireco.database import Database

@pytest.fixture
def db():
    database = Database(':memory:')
    database.create_tables()
    yield database
    database.close()

@pytest.fixture
def sample_user():
    return User(name="John", email="john@example.com")
```

## Mocking

### Using unittest.mock

```python
from unittest.mock import Mock, patch, MagicMock

def test_api_call():
    with patch('requests.get') as mock_get:
        mock_get.return_value.json.return_value = {'data': 'test'}
        result = fetch_data('http://api.example.com')
        assert result['data'] == 'test'
```

### Using pytest-mock

```python
def test_with_mocker(mocker):
    mock_method = mocker.patch('module.method')
    mock_method.return_value = 'mocked'
    
    result = call_method()
    assert result == 'mocked'
```

## Testing Async Code

```python
import pytest
import asyncio

@pytest.mark.asyncio
async def test_async_function():
    result = await async_add(2, 3)
    assert result == 5

@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
```

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=portunix-ireco

# Run specific test file
pytest tests/test_calculator.py

# Run with verbose output
pytest -v

# Run tests matching pattern
pytest -k "test_add"
```

## Configuration

### pytest.ini

```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = --strict-markers --disable-warnings
markers =
    slow: marks tests as slow
    integration: marks tests as integration tests
    unit: marks tests as unit tests
```

## Best Practices

- Use descriptive test names
- Keep tests simple and focused
- Use fixtures for setup/teardown
- Mock external dependencies
- Aim for high test coverage (>90%)
- Use parametrized tests for multiple scenarios
- Test both success and failure cases

---

*Python's rich testing ecosystem supports comprehensive test strategies.*
