# Java Code Style Guide for portunix-ireco

## Overview

This document defines the Java coding standards for the portunix-ireco project.

## General Principles

- Follow [Google Java Style Guide](https://google.github.io/styleguide/javaguide.html) as baseline
- Write clean, readable, and maintainable code
- Favor composition over inheritance
- Use meaningful names

## Naming Conventions

### Packages

- All lowercase, no underscores
- Use reversed domain name: `com.organization.portunix-ireco`
- Keep package names short and meaningful

### Classes and Interfaces

- Use PascalCase: `UserService`, `DataProcessor`
- Interfaces: consider 'I' prefix or descriptive names: `IUserService` or `UserService`
- Implementation classes: `UserServiceImpl` or specific name like `DatabaseUserService`
- Abstract classes: prefix with 'Abstract': `AbstractController`

### Methods

- Use camelCase: `getUserById()`, `calculateTotal()`
- Boolean methods: use is/has/can prefix: `isValid()`, `hasPermission()`
- Getters/setters: `getName()`, `setName()`

### Variables

- Use camelCase: `userName`, `totalAmount`
- Constants: UPPER_SNAKE_CASE: `MAX_RETRY_COUNT`
- Avoid single letter names except for loop counters

### Generics

- Single uppercase letter for simple types: `T`, `E`, `K`, `V`
- Descriptive names for complex types: `RequestType`, `ResponseType`

## Code Formatting

### Indentation

- Use 4 spaces (no tabs)
- Continuation indent: 8 spaces

### Line Length

- Maximum 120 characters
- Break at logical points

### Braces

```java
// Always use braces, even for single statements
if (condition) {
    doSomething();
}

// Class and method declarations
public class MyClass {
    public void myMethod() {
        // code
    }
}
```

### Whitespace

```java
// Space after keywords
if (condition) {
    // code
}

// Space around operators
int sum = a + b;

// No space before semicolon
for (int i = 0; i < 10; i++) {
    // code
}
```

## Comments and Documentation

### Javadoc

```java
/**
 * Brief description of the class.
 * 
 * <p>More detailed description if needed.
 * 
 * @author Author Name
 * @since 1.0
 */
public class UserService {
    
    /**
     * Retrieves a user by their ID.
     * 
     * @param userId the ID of the user to retrieve
     * @return the user object, or null if not found
     * @throws IllegalArgumentException if userId is null or empty
     * @throws DataAccessException if database error occurs
     */
    public User getUserById(String userId) {
        // implementation
    }
}
```

### Inline Comments

```java
// Use single-line comments for brief explanations
int retries = 3; // Maximum number of retry attempts

/*
 * Use block comments for longer explanations
 * that span multiple lines
 */
```

## Project Structure

```text
portunix-ireco/
├── src/
│   ├── main/
│   │   ├── java/
│   │   │   └── com/organization/portunix-ireco/
│   │   │       ├── controller/
│   │   │       ├── service/
│   │   │       ├── repository/
│   │   │       ├── model/
│   │   │       ├── dto/
│   │   │       ├── exception/
│   │   │       └── util/
│   │   └── resources/
│   └── test/
│       ├── java/
│       └── resources/
├── pom.xml or build.gradle
└── README.md
```

## Best Practices

### Class Design

```java
public class User {
    // Constants first
    private static final int MAX_NAME_LENGTH = 100;
    
    // Static fields
    private static int userCount = 0;
    
    // Instance fields
    private final String id;
    private String name;
    private String email;
    
    // Constructors
    public User(String id) {
        this.id = id;
    }
    
    // Static methods
    public static int getUserCount() {
        return userCount;
    }
    
    // Instance methods
    public String getName() {
        return name;
    }
    
    // Inner classes at the end
    private static class UserBuilder {
        // builder implementation
    }
}
```

### Exception Handling

```java
// Be specific with exceptions
try {
    processData();
} catch (IOException e) {
    logger.error("Failed to read file: {}", filename, e);
    throw new DataProcessingException("Unable to process file: " + filename, e);
} catch (ParseException e) {
    logger.error("Invalid data format in file: {}", filename, e);
    throw new DataProcessingException("Invalid format in file: " + filename, e);
}

// Use try-with-resources
try (InputStream input = new FileInputStream(file)) {
    return processInputStream(input);
}
```

### Collections and Streams

```java
// Use diamond operator
List<String> names = new ArrayList<>();

// Prefer immutable collections
List<String> immutableList = Collections.unmodifiableList(names);

// Use streams appropriately
List<String> filtered = users.stream()
    .filter(User::isActive)
    .map(User::getName)
    .sorted()
    .collect(Collectors.toList());

// Don't overuse streams for simple operations
// Good for simple loop
for (User user : users) {
    processUser(user);
}
```

### Annotations

```java
@Service
@Transactional
public class UserService {
    
    @Autowired
    private UserRepository userRepository;
    
    @Override
    @Cacheable("users")
    public User findById(@NonNull String id) {
        return userRepository.findById(id);
    }
}
```

## Testing

### Test Naming

```java
@Test
public void getUserById_WhenUserExists_ReturnsUser() {
    // Given
    String userId = "123";
    User expectedUser = new User(userId);
    when(userRepository.findById(userId)).thenReturn(expectedUser);
    
    // When
    User actualUser = userService.getUserById(userId);
    
    // Then
    assertEquals(expectedUser, actualUser);
}

@Test(expected = IllegalArgumentException.class)
public void getUserById_WhenIdIsNull_ThrowsException() {
    userService.getUserById(null);
}
```

### Test Organization

- One test class per production class
- Use `@Before` and `@After` for setup/teardown
- Group related tests with nested classes (JUnit 5)
- Use meaningful test data

## Modern Java Features

### Optional

```java
public Optional<User> findUser(String id) {
    return Optional.ofNullable(userRepository.findById(id));
}

// Usage
findUser(id)
    .map(User::getName)
    .orElse("Unknown");
```

### Lambda Expressions

```java
// Prefer method references when possible
list.forEach(System.out::println);

// Use lambdas for complex logic
list.stream()
    .filter(s -> s.length() > 5 && s.startsWith("A"))
    .collect(Collectors.toList());
```

### Records (Java 14+)

```java
public record UserDto(String id, String name, String email) {
    // Compact constructor for validation
    public UserDto {
        Objects.requireNonNull(id, "ID cannot be null");
        Objects.requireNonNull(email, "Email cannot be null");
    }
}
```

## Dependencies and Build

### Maven/Gradle

- Declare versions in properties/variables
- Use dependency management
- Exclude unnecessary transitive dependencies
- Keep dependencies up to date

### Logging

```java
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class UserService {
    private static final Logger logger = LoggerFactory.getLogger(UserService.class);
    
    public void processUser(User user) {
        logger.debug("Processing user: {}", user.getId());
        try {
            // processing logic
            logger.info("Successfully processed user: {}", user.getId());
        } catch (Exception e) {
            logger.error("Failed to process user: {}", user.getId(), e);
        }
    }
}
```

## Code Example

```java
package com.organization.portunix-ireco.service;

import com.organization.portunix-ireco.model.User;
import com.organization.portunix-ireco.repository.UserRepository;
import com.organization.portunix-ireco.exception.UserNotFoundException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Optional;
import java.util.Objects;

/**
 * Service class for managing users.
 * 
 * @author portunix-ireco Team
 * @since 1.0
 */
@Service
@Transactional
public class UserService {
    
    private static final Logger logger = LoggerFactory.getLogger(UserService.class);
    
    private final UserRepository userRepository;
    
    public UserService(UserRepository userRepository) {
        this.userRepository = Objects.requireNonNull(userRepository, 
            "UserRepository cannot be null");
    }
    
    /**
     * Finds a user by their ID.
     * 
     * @param userId the user ID
     * @return the user
     * @throws UserNotFoundException if user not found
     */
    public User findById(String userId) {
        logger.debug("Finding user by id: {}", userId);
        
        return userRepository.findById(userId)
            .orElseThrow(() -> new UserNotFoundException(
                "User not found with id: " + userId));
    }
    
    /**
     * Creates a new user.
     * 
     * @param user the user to create
     * @return the created user
     */
    public User createUser(User user) {
        Objects.requireNonNull(user, "User cannot be null");
        logger.info("Creating new user: {}", user.getEmail());
        
        return userRepository.save(user);
    }
}
```

## Tools and Automation

### IDE Configuration

- Use IDE code style settings
- Enable save actions (format, organize imports)
- Configure inspection profiles

### Static Analysis

- Use SpotBugs, PMD, or SonarQube
- Configure Checkstyle with project rules
- Run analysis in CI/CD pipeline

### Build Tools

```xml
<!-- Maven plugins -->
<plugin>
    <groupId>org.apache.maven.plugins</groupId>
    <artifactId>maven-checkstyle-plugin</artifactId>
</plugin>
```

## References

- [Google Java Style Guide](https://google.github.io/styleguide/javaguide.html)
- [Oracle Java Code Conventions](https://www.oracle.com/java/technologies/javase/codeconventions-contents.html)
- [Effective Java by Joshua Bloch](https://www.oreilly.com/library/view/effective-java/9780134686097/)
- Project-specific requirements in CONTRIBUTING.md
