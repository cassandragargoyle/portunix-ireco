# Python Code Style Guide for portunix-ireco

## Overview

This document defines the Python coding standards for the portunix-ireco project.

## General Principles

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) as the base style guide
- Write Pythonic code - embrace Python idioms
- Prioritize readability and simplicity
- Use type hints for better code documentation

## Naming Conventions

### Modules and Packages

- Use lowercase with underscores: `user_service.py`, `data_processor.py`
- Keep names short and descriptive
- Avoid using names that conflict with built-in modules

### Classes

- Use PascalCase: `UserManager`, `DataProcessor`
- Exception classes should end with "Error": `ValidationError`

### Functions and Variables

- Use snake_case: `calculate_total()`, `user_name`
- Private functions/methods: prefix with underscore: `_internal_method()`
- "Really" private: double underscore: `__private_method()`

### Constants

- Use UPPER_SNAKE_CASE: `MAX_CONNECTIONS`, `DEFAULT_TIMEOUT`
- Define at module level

### Type Variables

```python
from typing import TypeVar

T = TypeVar('T')  # Generic type
UserType = TypeVar('UserType', bound='User')  # Bounded type
```

## Code Formatting

### Indentation

- Use 4 spaces (no tabs)
- Continuation lines should align with opening delimiter

```python
# Aligned with opening delimiter
def long_function_name(var_one, var_two,
                       var_three, var_four):
    print(var_one)

# Hanging indent
def long_function_name(
        var_one, var_two, var_three,
        var_four):
    print(var_one)
```

### Line Length

- Maximum 120 characters (relaxed from PEP 8's 79)
- Break lines at logical points
- Use parentheses for implicit line continuation

### Imports

```python
# Standard library imports
import os
import sys
from datetime import datetime
from typing import List, Optional, Dict

# Third-party imports
import numpy as np
import pandas as pd
from flask import Flask, request

# Local imports
from portunix-ireco.models import User
from portunix-ireco.services import UserService
from portunix-ireco.utils.helpers import validate_email
```

### Whitespace

```python
# Good
spam(ham[1], {eggs: 2})
if x == 4:
    print(x, y)
    x, y = y, x

# Bad
spam( ham[ 1 ], { eggs: 2 } )
if x == 4 :
    print(x , y)
    x , y = y , x
```

## Type Hints

### Basic Types

```python
from typing import List, Dict, Optional, Union, Any, Tuple

def process_user(
    name: str,
    age: int,
    emails: List[str],
    metadata: Optional[Dict[str, Any]] = None
) -> Tuple[bool, str]:
    """Process user data and return status."""
    return True, "Success"
```

### Complex Types

```python
from typing import TypedDict, Protocol, Callable

class UserDict(TypedDict):
    name: str
    age: int
    email: str

class Processor(Protocol):
    def process(self, data: str) -> str:
        ...

ProcessorFunc = Callable[[str], str]
```

## Documentation

### Module Docstrings

```python
"""
Module for handling user operations.

This module provides functionality for creating, updating,
and managing user accounts in the portunix-ireco system.

Examples:
    >>> from portunix-ireco.users import UserService
    >>> service = UserService()
    >>> user = service.create_user("John", "john@example.com")
"""
```

### Function/Method Docstrings

```python
def calculate_discount(
    price: float,
    discount_percent: float,
    max_discount: Optional[float] = None
) -> float:
    """
    Calculate the discounted price.
    
    Args:
        price: Original price of the item
        discount_percent: Discount percentage (0-100)
        max_discount: Maximum discount amount allowed
    
    Returns:
        The final price after applying discount
    
    Raises:
        ValueError: If discount_percent is not between 0 and 100
    
    Examples:
        >>> calculate_discount(100, 20)
        80.0
        >>> calculate_discount(100, 50, max_discount=30)
        70.0
    """
    if not 0 <= discount_percent <= 100:
        raise ValueError("Discount must be between 0 and 100")
    
    discount = price * (discount_percent / 100)
    if max_discount:
        discount = min(discount, max_discount)
    
    return price - discount
```

### Class Docstrings

```python
class UserService:
    """
    Service for managing user operations.
    
    This class provides methods for creating, updating, and
    deleting users in the system.
    
    Attributes:
        repository: The user repository instance
        cache: Optional cache for user data
    
    Examples:
        >>> service = UserService(repository)
        >>> user = service.get_user("123")
    """
    
    def __init__(self, repository: UserRepository, cache: Optional[Cache] = None):
        """
        Initialize the UserService.
        
        Args:
            repository: Repository for user data persistence
            cache: Optional cache instance for performance
        """
        self.repository = repository
        self.cache = cache
```

## Project Structure

```text
portunix-ireco/
├── src/
│   └── portunix-ireco/
│       ├── __init__.py
│       ├── __main__.py
│       ├── api/
│       │   ├── __init__.py
│       │   └── routes.py
│       ├── models/
│       │   ├── __init__.py
│       │   └── user.py
│       ├── services/
│       │   ├── __init__.py
│       │   └── user_service.py
│       ├── utils/
│       │   ├── __init__.py
│       │   └── helpers.py
│       └── config.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   └── integration/
├── docs/
├── requirements.txt
├── requirements-dev.txt
├── setup.py
├── pyproject.toml
└── README.md
```

## Best Practices

### Error Handling

```python
# Be specific with exceptions
try:
    process_data(data)
except FileNotFoundError as e:
    logger.error(f"File not found: {e.filename}")
    raise
except json.JSONDecodeError as e:
    logger.error(f"Invalid JSON at line {e.lineno}: {e.msg}")
    raise ValueError(f"Invalid JSON format") from e
except Exception as e:
    logger.exception("Unexpected error during processing")
    raise

# Custom exceptions
class UserNotFoundError(Exception):
    """Raised when a user cannot be found."""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        super().__init__(f"User not found: {user_id}")
```

### Context Managers

```python
from contextlib import contextmanager
from typing import Generator

@contextmanager
def database_connection() -> Generator[Connection, None, None]:
    """Context manager for database connections."""
    conn = create_connection()
    try:
        yield conn
    finally:
        conn.close()

# Usage
with database_connection() as conn:
    conn.execute("SELECT * FROM users")
```

### Decorators

```python
from functools import wraps
from typing import Callable, Any
import time

def retry(max_attempts: int = 3, delay: float = 1.0) -> Callable:
    """Retry decorator with exponential backoff."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    time.sleep(delay * (2 ** attempt))
            return None
        return wrapper
    return decorator

@retry(max_attempts=3, delay=1.0)
def fetch_data(url: str) -> Dict[str, Any]:
    """Fetch data from URL with retry logic."""
    return requests.get(url).json()
```

### List Comprehensions and Generators

```python
# Good - list comprehension for simple transformations
squares = [x**2 for x in range(10) if x % 2 == 0]

# Good - generator for memory efficiency
def process_large_file(filename: str) -> Generator[str, None, None]:
    with open(filename) as f:
        for line in f:
            if line.strip():
                yield line.strip().upper()

# Avoid complex comprehensions
# Bad
result = [process(x) for x in items if validate(x) and x.attr > 10 and x.status == 'active']

# Good
result = []
for item in items:
    if validate(item) and item.attr > 10 and item.status == 'active':
        result.append(process(item))
```

## Testing

### Test Structure

```python
import pytest
from unittest.mock import Mock, patch
from portunix-ireco.services import UserService

class TestUserService:
    """Test cases for UserService."""
    
    @pytest.fixture
    def service(self):
        """Create UserService instance for testing."""
        repository = Mock()
        return UserService(repository)
    
    def test_create_user_success(self, service):
        """Test successful user creation."""
        # Arrange
        user_data = {"name": "John", "email": "john@example.com"}
        expected_user = User(**user_data)
        service.repository.save.return_value = expected_user
        
        # Act
        result = service.create_user(**user_data)
        
        # Assert
        assert result == expected_user
        service.repository.save.assert_called_once()
    
    def test_create_user_invalid_email(self, service):
        """Test user creation with invalid email."""
        # Arrange
        user_data = {"name": "John", "email": "invalid"}
        
        # Act & Assert
        with pytest.raises(ValueError, match="Invalid email"):
            service.create_user(**user_data)
    
    @pytest.mark.parametrize("name,email,expected", [
        ("John", "john@example.com", True),
        ("", "john@example.com", False),
        ("John", "", False),
    ])
    def test_validate_user_data(self, service, name, email, expected):
        """Test user data validation with various inputs."""
        result = service.validate_user_data(name, email)
        assert result == expected
```

## Modern Python Features

### Dataclasses

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import List

@dataclass
class User:
    """User data model."""
    id: str
    name: str
    email: str
    created_at: datetime = field(default_factory=datetime.now)
    tags: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate data after initialization."""
        if not self.email or '@' not in self.email:
            raise ValueError("Invalid email address")
```

### Async/Await

```python
import asyncio
from typing import List

async def fetch_user(user_id: str) -> User:
    """Asynchronously fetch user data."""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"/api/users/{user_id}") as response:
            data = await response.json()
            return User(**data)

async def fetch_multiple_users(user_ids: List[str]) -> List[User]:
    """Fetch multiple users concurrently."""
    tasks = [fetch_user(uid) for uid in user_ids]
    return await asyncio.gather(*tasks)
```

### Pattern Matching (Python 3.10+)

```python
def process_command(command: dict) -> str:
    """Process command using pattern matching."""
    match command:
        case {"action": "create", "type": "user", "data": data}:
            return create_user(data)
        case {"action": "delete", "type": "user", "id": user_id}:
            return delete_user(user_id)
        case {"action": "update", "type": type_, **kwargs}:
            return update_entity(type_, kwargs)
        case _:
            return "Unknown command"
```

## Code Example

```python
"""
User service module for portunix-ireco.

This module provides user management functionality including
creation, retrieval, update, and deletion of users.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
import logging
from dataclasses import dataclass, field

from portunix-ireco.models import User
from portunix-ireco.repositories import UserRepository
from portunix-ireco.exceptions import UserNotFoundError, ValidationError
from portunix-ireco.utils.validators import validate_email

logger = logging.getLogger(__name__)


@dataclass
class UserCreateRequest:
    """Request model for user creation."""
    name: str
    email: str
    password: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class UserService:
    """
    Service for managing users in portunix-ireco.
    
    This service provides high-level operations for user management,
    including validation, business logic, and data persistence.
    """
    
    def __init__(self, repository: UserRepository) -> None:
        """
        Initialize the UserService.
        
        Args:
            repository: Repository for user data persistence
        """
        self.repository = repository
        logger.info("UserService initialized")
    
    def create_user(self, request: UserCreateRequest) -> User:
        """
        Create a new user.
        
        Args:
            request: User creation request data
        
        Returns:
            The created user instance
        
        Raises:
            ValidationError: If user data is invalid
        """
        logger.debug(f"Creating user: {request.email}")
        
        # Validate input
        if not validate_email(request.email):
            raise ValidationError(f"Invalid email: {request.email}")
        
        # Check for existing user
        if self.repository.find_by_email(request.email):
            raise ValidationError(f"User already exists: {request.email}")
        
        # Create user
        user = User(
            name=request.name,
            email=request.email,
            password_hash=self._hash_password(request.password),
            metadata=request.metadata,
            created_at=datetime.now()
        )
        
        saved_user = self.repository.save(user)
        logger.info(f"User created successfully: {saved_user.id}")
        
        return saved_user
    
    def get_user(self, user_id: str) -> User:
        """
        Retrieve a user by ID.
        
        Args:
            user_id: The user's unique identifier
        
        Returns:
            The user instance
        
        Raises:
            UserNotFoundError: If user doesn't exist
        """
        user = self.repository.find_by_id(user_id)
        if not user:
            raise UserNotFoundError(user_id)
        return user
    
    def list_users(
        self,
        limit: int = 100,
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[User]:
        """
        List users with pagination and filtering.
        
        Args:
            limit: Maximum number of users to return
            offset: Number of users to skip
            filters: Optional filters to apply
        
        Returns:
            List of users matching the criteria
        """
        return self.repository.find_all(
            limit=limit,
            offset=offset,
            filters=filters or {}
        )
    
    def _hash_password(self, password: str) -> str:
        """Hash a password for secure storage."""
        # Implementation would use bcrypt or similar
        return f"hashed_{password}"
```

## Tools and Automation

### Linting and Formatting

```bash
# Format with black
black src/ tests/

# Sort imports with isort
isort src/ tests/

# Lint with flake8
flake8 src/ tests/

# Type check with mypy
mypy src/

# All-in-one with pre-commit
pre-commit run --all-files
```

### Pre-commit Configuration

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.1.0
    hooks:
      - id: black
  - repo: https://github.com/PyCQA/isort
    rev: 5.12.0
    hooks:
      - id: isort
  - repo: https://github.com/PyCQA/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.0.0
    hooks:
      - id: mypy
```

### Testing Commands

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=portunix-ireco --cov-report=html

# Run specific test file
pytest tests/test_user_service.py

# Run with verbose output
pytest -v

# Run only marked tests
pytest -m "unit"
```

## References

- [PEP 8 - Style Guide for Python Code](https://www.python.org/dev/peps/pep-0008/)
- [PEP 484 - Type Hints](https://www.python.org/dev/peps/pep-0484/)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [The Hitchhiker's Guide to Python](https://docs.python-guide.org/)
- Project-specific requirements in CONTRIBUTING.md
