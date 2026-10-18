# Java Testing Guide for portunix-ireco

## Overview

Testing strategy and frameworks for Java development in portunix-ireco.

## Testing Frameworks

### JUnit 5 (Recommended)

```java
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.BeforeEach;
import static org.junit.jupiter.api.Assertions.*;

class CalculatorTest {
    private Calculator calculator;
    
    @BeforeEach
    void setUp() {
        calculator = new Calculator();
    }
    
    @Test
    void testAddition() {
        assertEquals(4, calculator.add(2, 2));
    }
    
    @ParameterizedTest
    @ValueSource(ints = {1, 2, 3})
    void testWithParameters(int value) {
        assertTrue(value > 0);
    }
}
```

### Mockito for Mocking

```java
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class UserServiceTest {
    @Mock
    private UserRepository userRepository;
    
    @Test
    void testGetUser() {
        User mockUser = new User("John");
        when(userRepository.findById("1")).thenReturn(mockUser);
        
        UserService service = new UserService(userRepository);
        User result = service.getUser("1");
        
        assertEquals("John", result.getName());
        verify(userRepository).findById("1");
    }
}
```

## Test Categories

### Unit Tests

- Test individual components
- Use mocks for dependencies
- Fast execution
- High coverage

### Integration Tests

```java
@SpringBootTest
@AutoConfigureTestDatabase
class UserControllerIntegrationTest {
    @Autowired
    private TestRestTemplate restTemplate;
    
    @Test
    void testCreateUser() {
        User user = new User("John");
        ResponseEntity<User> response = restTemplate.postForEntity(
            "/users", user, User.class);
        assertEquals(HttpStatus.CREATED, response.getStatusCode());
    }
}
```

## Running Tests

```bash
# Maven
mvn test
mvn test -Dtest=UserServiceTest

# Gradle
./gradlew test
./gradlew test --tests UserServiceTest
```

## Best Practices

- Use descriptive test method names
- Follow AAA pattern (Arrange, Act, Assert)
- Test edge cases and error conditions
- Keep tests independent
- Use @DisplayName for better test reports

---

*Comprehensive testing ensures robust Java applications.*
