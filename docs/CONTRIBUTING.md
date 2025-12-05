# Contributing to Telegram Bot Control Panel

Thank you for your interest in contributing to the Telegram Bot Control Panel! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Development Setup](#development-setup)
4. [Coding Standards](#coding-standards)
5. [Testing Guidelines](#testing-guidelines)
6. [Submitting Changes](#submitting-changes)
7. [Documentation](#documentation)
8. [Community](#community)

## Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inclusive environment for all contributors, regardless of:
- Experience level
- Gender identity and expression
- Sexual orientation
- Disability
- Personal appearance
- Body size
- Race
- Ethnicity
- Age
- Religion
- Nationality

### Our Standards

**Positive behavior includes:**
- Using welcoming and inclusive language
- Being respectful of differing viewpoints
- Gracefully accepting constructive criticism
- Focusing on what is best for the community
- Showing empathy towards other community members

**Unacceptable behavior includes:**
- Harassment, trolling, or insulting comments
- Public or private harassment
- Publishing others' private information
- Other conduct which could reasonably be considered inappropriate

## Getting Started

### Ways to Contribute

You can contribute in many ways:

1. **Report Bugs** - Found a bug? Let us know!
2. **Suggest Features** - Have an idea? Share it!
3. **Fix Issues** - Pick an issue and submit a fix
4. **Improve Documentation** - Help others understand the project
5. **Write Tests** - Increase test coverage
6. **Review Pull Requests** - Help review others' contributions

### Before You Start

1. **Check existing issues** - Someone might already be working on it
2. **Discuss major changes** - Open an issue first for big changes
3. **Read the documentation** - Understand the project architecture
4. **Set up your environment** - Follow the development setup guide

## Development Setup

### Prerequisites

- Python 3.9 or higher
- Git
- Virtual environment tool (venv or virtualenv)
- Text editor or IDE (VS Code, PyCharm recommended)

### Setup Steps

1. **Fork the repository**
   ```bash
   # Click "Fork" on GitHub, then clone your fork
   git clone https://github.com/YOUR_USERNAME/advertise-bot.git
   cd advertise-bot
   ```

2. **Add upstream remote**
   ```bash
   git remote add upstream https://github.com/ali-moments/advertise-bot.git
   ```

3. **Create virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

4. **Install dependencies**
   ```bash
   # Install production dependencies
   pip install -r requirements.txt
   
   # Install development dependencies
   pip install -r requirements-dev.txt
   ```

5. **Set up pre-commit hooks** (optional but recommended)
   ```bash
   pre-commit install
   ```

6. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your test credentials
   ```

7. **Run tests**
   ```bash
   pytest tests/
   ```

### Development Workflow

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Write code
   - Add tests
   - Update documentation

3. **Test your changes**
   ```bash
   # Run all tests
   pytest tests/
   
   # Run specific test file
   pytest tests/test_bot_integration.py
   
   # Run with coverage
   pytest --cov=panel tests/
   ```

4. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat: add new feature"
   ```

5. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Create pull request**
   - Go to GitHub
   - Click "New Pull Request"
   - Fill in the template
   - Submit for review

## Coding Standards

### Python Style Guide

We follow [PEP 8](https://pep8.org/) with some modifications:

**Line Length:**
- Maximum 100 characters (not 79)
- Break long lines logically

**Naming Conventions:**
```python
# Classes: PascalCase
class ScrapingHandler:
    pass

# Functions/methods: snake_case
def handle_scraping():
    pass

# Constants: UPPER_SNAKE_CASE
MAX_RETRIES = 3

# Private methods: _leading_underscore
def _internal_method():
    pass
```

**Imports:**
```python
# Standard library
import os
import sys

# Third-party
from telegram import Update
from telegram.ext import ContextTypes

# Local
from panel.config import Config
from panel.state_manager import StateManager
```

**Type Hints:**
```python
def process_data(
    data: List[Dict[str, Any]],
    timeout: Optional[int] = None
) -> Tuple[bool, str]:
    pass
```

**Docstrings:**
```python
def complex_function(param1: str, param2: int) -> bool:
    """
    Brief description of what the function does.
    
    Args:
        param1: Description of param1
        param2: Description of param2
    
    Returns:
        Description of return value
    
    Raises:
        ValueError: When param2 is negative
    
    Example:
        >>> complex_function("test", 5)
        True
    """
    pass
```

### Code Quality Tools

**Linting:**
```bash
# Run flake8
flake8 panel/ tests/

# Run pylint
pylint panel/ tests/

# Run mypy for type checking
mypy panel/
```

**Formatting:**
```bash
# Format with black
black panel/ tests/

# Sort imports with isort
isort panel/ tests/
```

**Pre-commit:**
```bash
# Run all pre-commit hooks
pre-commit run --all-files
```

### Best Practices

**1. Keep functions small and focused**
```python
# Good
def validate_user_id(user_id: int) -> bool:
    return user_id in ADMIN_USERS

# Bad - does too much
def validate_and_process_user(user_id: int, data: Dict) -> Any:
    if user_id not in ADMIN_USERS:
        return False
    # ... 50 more lines
```

**2. Use meaningful variable names**
```python
# Good
total_messages_sent = 0
recipient_list = []

# Bad
x = 0
lst = []
```

**3. Handle errors explicitly**
```python
# Good
try:
    result = risky_operation()
except SpecificError as e:
    logger.error(f"Operation failed: {e}")
    raise

# Bad
try:
    result = risky_operation()
except:
    pass
```

**4. Write self-documenting code**
```python
# Good
if user_has_permission(user_id, "admin"):
    allow_access()

# Bad
if check(uid, "a"):
    do_thing()
```

**5. Use constants for magic numbers**
```python
# Good
MAX_RETRIES = 3
TIMEOUT_SECONDS = 30

# Bad
for i in range(3):
    time.sleep(30)
```

## Testing Guidelines

### Test Structure

```
tests/
├── test_bot_integration.py      # Bot integration tests
├── test_handlers.py              # Handler unit tests
├── test_ui_components.py         # UI component tests
├── test_state_manager.py         # State management tests
├── test_file_handler.py          # File operation tests
└── test_property_*.py            # Property-based tests
```

### Writing Tests

**Unit Test Example:**
```python
import pytest
from panel.keyboard_builder import KeyboardBuilder

class TestKeyboardBuilder:
    def test_main_menu_creates_keyboard(self):
        """Test that main menu creates a valid keyboard."""
        keyboard = KeyboardBuilder.main_menu()
        
        assert keyboard is not None
        assert len(keyboard.inline_keyboard) > 0
        assert all(len(row) > 0 for row in keyboard.inline_keyboard)
    
    def test_confirm_cancel_has_two_buttons(self):
        """Test that confirm/cancel keyboard has exactly 2 buttons."""
        keyboard = KeyboardBuilder.confirm_cancel("yes", "no")
        
        assert len(keyboard.inline_keyboard) == 1
        assert len(keyboard.inline_keyboard[0]) == 2
```

**Async Test Example:**
```python
import pytest
from unittest.mock import Mock, AsyncMock

@pytest.mark.asyncio
async def test_scraping_handler():
    """Test scraping handler processes groups correctly."""
    # Setup
    manager = Mock()
    manager.bulk_scrape_groups = AsyncMock(return_value={
        'success': True,
        'groups_scraped': 5
    })
    
    handler = ScrapingHandler(manager)
    
    # Execute
    result = await handler.execute_scrape(['@group1', '@group2'])
    
    # Verify
    assert result['success'] is True
    assert manager.bulk_scrape_groups.called
```

**Property-Based Test Example:**
```python
from hypothesis import given, strategies as st

@given(st.integers(min_value=1, max_value=10))
def test_delay_validation_accepts_valid_range(delay):
    """Test that delay validation accepts values in valid range."""
    is_valid, _ = Validators.validate_delay(delay)
    assert is_valid is True

@given(st.integers(min_value=-100, max_value=0))
def test_delay_validation_rejects_invalid_range(delay):
    """Test that delay validation rejects values outside valid range."""
    is_valid, _ = Validators.validate_delay(delay)
    assert is_valid is False
```

### Test Coverage

**Minimum Requirements:**
- Overall coverage: 80%+
- New code coverage: 90%+
- Critical paths: 100%

**Check Coverage:**
```bash
# Generate coverage report
pytest --cov=panel --cov-report=html tests/

# View report
open htmlcov/index.html
```

### Test Best Practices

1. **Test one thing per test**
2. **Use descriptive test names**
3. **Follow AAA pattern** (Arrange, Act, Assert)
4. **Use fixtures for common setup**
5. **Mock external dependencies**
6. **Test edge cases and error conditions**
7. **Keep tests fast** (< 1 second each)

## Submitting Changes

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

**Format:**
```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**
```
feat(scraping): add link extraction feature

Implement link extraction from channels that scans recent messages
for Telegram group/channel links and offers to scrape them.

Closes #123
```

```
fix(sending): handle rate limit errors gracefully

Add exponential backoff for rate limit errors during bulk sending
to prevent operation failures.

Fixes #456
```

### Pull Request Process

1. **Update documentation** if needed
2. **Add tests** for new features
3. **Ensure all tests pass**
4. **Update CHANGELOG.md**
5. **Fill in PR template completely**
6. **Request review** from maintainers
7. **Address review comments**
8. **Wait for approval** before merging

### Pull Request Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing performed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex code
- [ ] Documentation updated
- [ ] No new warnings generated
- [ ] Tests pass locally

## Related Issues
Closes #(issue number)

## Screenshots (if applicable)
```

## Documentation

### Documentation Standards

**Code Documentation:**
- All public functions/classes must have docstrings
- Complex logic should have inline comments
- Use type hints for function signatures

**User Documentation:**
- Update USER_GUIDE.md for user-facing changes
- Update API.md for API changes
- Update FAQ.md for common questions

**Developer Documentation:**
- Update ARCHITECTURE.md for architectural changes
- Update this file for process changes
- Add examples for new features

### Documentation Style

**Markdown:**
- Use ATX-style headers (`#` not `===`)
- Use fenced code blocks with language
- Use tables for structured data
- Include examples where helpful

**Code Examples:**
```python
# Always include:
# 1. Imports
# 2. Setup code
# 3. Main example
# 4. Expected output

from panel.keyboard_builder import KeyboardBuilder

# Create main menu keyboard
keyboard = KeyboardBuilder.main_menu()

# Use in bot
await update.message.reply_text(
    "منوی اصلی",
    reply_markup=keyboard
)
```

## Community

### Communication Channels

- **GitHub Issues** - Bug reports, feature requests
- **GitHub Discussions** - General questions, ideas
- **Pull Requests** - Code review, discussions
- **Email** - Private/security issues

### Getting Help

**For Contributors:**
1. Check existing documentation
2. Search closed issues
3. Ask in GitHub Discussions
4. Contact maintainers

**For Users:**
1. Check USER_GUIDE.md
2. Check FAQ.md
3. Search existing issues
4. Open new issue with template

### Recognition

Contributors are recognized in:
- CONTRIBUTORS.md file
- Release notes
- Project README
- Annual contributor highlights

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.

## Questions?

If you have questions about contributing:
1. Check this document
2. Search existing issues
3. Open a discussion on GitHub
4. Contact the maintainers

Thank you for contributing to the Telegram Bot Control Panel!

