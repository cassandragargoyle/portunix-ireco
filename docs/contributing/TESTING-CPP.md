# C++ Testing Guide for portunix-ireco

## Overview

Testing strategy and guidelines for C++ development in portunix-ireco.

## Testing Frameworks

### Google Test (Recommended)

```cpp
#include <gtest/gtest.h>

TEST(CalculatorTest, Addition) {
    Calculator calc;
    EXPECT_EQ(4, calc.add(2, 2));
}
```

### Catch2 (Alternative)

```cpp
#include <catch2/catch.hpp>

TEST_CASE("Calculator addition", "[calculator]") {
    Calculator calc;
    REQUIRE(calc.add(2, 2) == 4);
}
```

## Test Structure

### Directory Layout

```text
tests/
├── unit/           # Unit tests
├── integration/    # Integration tests
├── fixtures/       # Test data
├── mocks/          # Mock objects
└── utils/          # Test utilities
```

### Test Naming

- File: `test_<component>.cpp`
- Class: `<Component>Test`
- Method: `Test<Scenario><Expected>`

## Best Practices

### Unit Tests

- Test single functionality
- Use mocks for dependencies
- Cover edge cases
- Maintain 80%+ coverage

### Integration Tests

- Test component interactions
- Use real dependencies where possible
- Focus on critical paths

### Performance Tests

```cpp
TEST(PerformanceTest, LargeDataSet) {
    auto start = std::chrono::high_resolution_clock::now();
    processLargeData();
    auto end = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end - start);
    EXPECT_LT(duration.count(), 1000); // Less than 1 second
}
```

## Running Tests

```bash
mkdir build && cd build
cmake ..
make test
```

---

*Comprehensive testing ensures code quality and reliability.*
