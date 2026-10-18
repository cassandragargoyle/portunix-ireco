# C++ Code Style Guide for portunix-ireco

## Overview

This document defines the C++ coding standards for the portunix-ireco project.

## Naming Conventions

### Classes and Structs

- Use PascalCase: `MyClass`, `DataProcessor`
- Interface classes should start with 'I': `IObserver`, `ISerializer`

### Functions and Methods

- Use camelCase: `calculateTotal()`, `getUserName()`
- Getters/setters: `getName()`, `setName()`

### Variables

- Local variables: camelCase - `localVariable`
- Member variables: m_ prefix with camelCase - `m_memberVariable`
- Constants: UPPER_SNAKE_CASE - `MAX_BUFFER_SIZE`
- Global variables (avoid): g_ prefix - `g_globalVariable`

### Namespaces

- Use lowercase with underscores: `my_namespace`

### Files

- Header files: `.h` or `.hpp`
- Source files: `.cpp`
- Use lowercase with underscores: `my_class.cpp`

## Code Formatting

### Indentation

- Use 4 spaces (no tabs)
- Namespace content is not indented

### Braces

```cpp
// Allman style (preferred)
if (condition)
{
    // code
}

// OR K&R style (acceptable)
if (condition) {
    // code
}
```

### Line Length

- Maximum 120 characters per line
- Break long lines at logical points

## Comments

### File Headers

```cpp
/**
 * @file my_class.cpp
 * @brief Brief description of file purpose
 * @author Author Name
 * @date 2024-01-01
 */
```

### Function Documentation

```cpp
/**
 * @brief Calculate the sum of two numbers
 * @param a First number
 * @param b Second number
 * @return Sum of a and b
 */
int add(int a, int b);
```

### Inline Comments

```cpp
// Single line comment
int value = 42; // Trailing comment

/* Multi-line comment
   for longer explanations */
```

## Best Practices

### Headers

- Use include guards or `#pragma once`
- Order includes: own headers, standard library, third-party

```cpp
#pragma once

#include "my_class.h"
#include <iostream>
#include <vector>
#include <boost/algorithm/string.hpp>
```

### Memory Management

- Prefer RAII and smart pointers
- Use `std::unique_ptr` for single ownership
- Use `std::shared_ptr` for shared ownership
- Avoid raw `new`/`delete`

### Modern C++ Features

- Use `auto` for complex type declarations
- Use range-based for loops
- Use `nullptr` instead of `NULL`
- Use `override` and `final` keywords
- Prefer `using` over `typedef`

### Error Handling

- Use exceptions for exceptional conditions
- Use error codes for expected failures
- Always check return values
- Use RAII for resource management

## Project-Specific Conventions

### Build System

- CMake for build configuration
- Separate src/, include/, test/ directories

### Testing

- Unit tests with Google Test or Catch2
- Test file naming: `test_<component>.cpp`
- Minimum 80% code coverage

### Dependencies

- Manage with vcpkg, Conan, or CMake FetchContent
- Document all external dependencies

## Code Example

```cpp
#pragma once

#include <string>
#include <memory>

namespace portunix-ireco
{

/**
 * @brief Example class demonstrating code style
 */
class ExampleClass
{
public:
    ExampleClass();
    explicit ExampleClass(const std::string& name);
    virtual ~ExampleClass() = default;

    // Getters/Setters
    const std::string& getName() const { return m_name; }
    void setName(const std::string& name) { m_name = name; }

    // Public methods
    void processData();
    int calculateResult(int input) const;

private:
    std::string m_name;
    int m_counter{0};
    
    static constexpr int MAX_COUNT = 100;
};

} // namespace portunix-ireco
```

## Tools and Automation

### Code Formatting Tools

- Use clang-format with project `.clang-format` file
- Format on save in IDE

### Static Analysis

- Use clang-tidy
- Run cppcheck regularly
- Address all compiler warnings

### Continuous Integration

- Build with multiple compilers (GCC, Clang, MSVC)
- Run tests on all platforms
- Enforce style checks in CI

## References

- [C++ Core Guidelines](https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines)
- [Google C++ Style Guide](https://google.github.io/styleguide/cppguide.html)
- Project-specific requirements in CONTRIBUTING.md
