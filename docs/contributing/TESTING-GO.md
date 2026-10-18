# Go Testing Guide for portunix-ireco

## Overview

Testing strategy and best practices for Go development in portunix-ireco.

## Built-in Testing

### Basic Test

```go
package main

import "testing"

func TestAdd(t *testing.T) {
    result := add(2, 3)
    expected := 5
    if result != expected {
        t.Errorf("add(2, 3) = %d; want %d", result, expected)
    }
}
```

### Table-Driven Tests

```go
func TestCalculate(t *testing.T) {
    tests := []struct {
        name     string
        a, b     int
        expected int
    }{
        {"positive", 2, 3, 5},
        {"zero", 0, 5, 5},
        {"negative", -1, 1, 0},
    }
    
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            result := add(tt.a, tt.b)
            if result != tt.expected {
                t.Errorf("add(%d, %d) = %d; want %d", 
                    tt.a, tt.b, result, tt.expected)
            }
        })
    }
}
```

## Testing Tools

### Testify (Recommended)

```go
import (
    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/mock"
    "github.com/stretchr/testify/suite"
)

func TestUserService(t *testing.T) {
    assert := assert.New(t)
    user := User{Name: "John"}
    assert.Equal("John", user.Name)
}
```

### Mocking

```go
type MockUserRepository struct {
    mock.Mock
}

func (m *MockUserRepository) GetUser(id string) (*User, error) {
    args := m.Called(id)
    return args.Get(0).(*User), args.Error(1)
}
```

## Running Tests

```bash
# Run all tests
go test ./...

# Run with coverage
go test -cover ./...

# Run specific test
go test -run TestAdd

# Verbose output
go test -v ./...
```

## Best Practices

- Use table-driven tests for multiple scenarios
- Test happy path and error cases
- Use meaningful test names
- Keep tests simple and focused
- Mock external dependencies

---

*Go's built-in testing tools provide excellent support for reliable testing.*
