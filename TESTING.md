# VibeBlog Testing Guide

## Overview

VibeBlog has a comprehensive automated testing infrastructure covering both frontend and backend components.

## Test Coverage Status

[![Frontend Tests](https://github.com/YOUR_USERNAME/vibe-blog/actions/workflows/test-frontend.yml/badge.svg)](https://github.com/YOUR_USERNAME/vibe-blog/actions/workflows/test-frontend.yml)
[![Backend Tests](https://github.com/YOUR_USERNAME/vibe-blog/actions/workflows/test-backend.yml/badge.svg)](https://github.com/YOUR_USERNAME/vibe-blog/actions/workflows/test-backend.yml)
[![codecov](https://codecov.io/gh/YOUR_USERNAME/vibe-blog/branch/main/graph/badge.svg)](https://codecov.io/gh/YOUR_USERNAME/vibe-blog)

**Current Coverage:**
- **Frontend:** 98%+ (Target: 60%)
- **Backend:** 55%+ (Target: 55%)

## Frontend Testing

### Tech Stack
- **Framework:** Vitest + Vue Test Utils
- **Mocking:** MSW (Mock Service Worker)
- **Environment:** happy-dom

### Running Tests

```bash
cd frontend

# Run all tests
npm test

# Run tests with UI
npm run test:ui

# Generate coverage report
npm run test:coverage
```

### Test Structure

```
frontend/
├── __tests__/
│   ├── unit/
│   │   ├── helpers.test.ts       # Utility functions (26 tests)
│   │   ├── api.test.ts           # API service layer (27 tests)
│   │   └── useBlogDetail.test.ts # Composables (21 tests)
│   ├── integration/              # Component integration tests
│   └── __mocks__/
│       ├── api.ts                # API mocks
│       └── stores.ts             # Pinia store mocks
├── vitest.config.ts              # Vitest configuration
└── vitest.setup.ts               # Test environment setup
```

### What's Tested (P0 - Priority 0)

✅ **Utility Functions** (`src/utils/helpers.ts`)
- File size formatting
- Word count formatting
- Status text/icons
- Cookie parsing
- HTML escaping
- Clipboard operations

✅ **API Service** (`src/services/api.ts`)
- Blog generation endpoints
- History management
- Document upload
- Configuration APIs
- XHS (Xiaohongshu) APIs
- Error handling

✅ **Composables** (`src/composables/useBlogDetail.ts`)
- Blog data loading
- Date/word count formatting
- Toast notifications
- Favorite toggling

### Writing New Tests

```typescript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import MyComponent from '@/components/MyComponent.vue'

describe('MyComponent', () => {
  it('should render correctly', () => {
    const wrapper = mount(MyComponent, {
      props: { title: 'Test' }
    })
    expect(wrapper.text()).toContain('Test')
  })
})
```

## Backend Testing

### Tech Stack
- **Framework:** pytest
- **Coverage:** pytest-cov
- **Mocking:** pytest-mock
- **Async:** pytest-asyncio

### Running Tests

```bash
cd backend

# Run all tests (skip LLM tests)
pytest

# Run with coverage
pytest --cov

# Run specific test file
pytest tests/unit/test_database_service.py

# Run tests with specific marker
pytest -m "unit"  # Only unit tests
pytest -m "not llm"  # Skip LLM tests (default in CI)

# Generate HTML coverage report
pytest --cov --cov-report=html
open htmlcov/index.html
```

### Test Structure

```
backend/
├── tests/
│   ├── unit/                     # Unit tests
│   ├── integration/              # Integration tests
│   ├── api/                      # API endpoint tests
│   └── fixtures/                 # Test fixtures
├── conftest.py                   # Shared fixtures
├── pytest.ini                    # Pytest configuration
└── .coveragerc                   # Coverage configuration
```

### Test Markers

Tests are categorized using pytest markers:

- `@pytest.mark.unit` - Fast unit tests, no external dependencies
- `@pytest.mark.integration` - Integration tests (database, file system)
- `@pytest.mark.api` - API endpoint tests
- `@pytest.mark.llm` - Tests requiring LLM API calls (expensive, skipped in CI)
- `@pytest.mark.slow` - Slow tests (skip by default)

### What's Tested (P0 - Priority 0)

✅ **Database Service** (`services/database_service.py`)
- CRUD operations
- History record management
- Document storage
- Book/chapter management

✅ **LLM Service** (`services/llm_service.py`)
- LLM API calls (mocked)
- Error handling
- Retry logic

✅ **Blog Generator** (`services/blog_generator/generator.py`)
- Blog generation workflow
- Revision logic
- Mini mode

### Writing New Tests

```python
import pytest
from services.database_service import DatabaseService

@pytest.mark.unit
def test_create_history_record(mock_db):
    """Test creating a history record"""
    service = DatabaseService(":memory:")
    record_id = service.create_history_record(
        topic="Test Topic",
        content="Test Content"
    )
    assert record_id is not None

    # Verify record was created
    record = service.get_history_record(record_id)
    assert record['topic'] == "Test Topic"
```

## CI/CD Integration

### GitHub Actions Workflows

**Frontend Tests** (`.github/workflows/test-frontend.yml`)
- Triggers on push/PR to `main`, `develop`, `feature/**`
- Runs on Node.js 18.x and 20.x
- Generates coverage report
- Uploads to Codecov
- Comments PR with coverage stats

**Backend Tests** (`.github/workflows/test-backend.yml`)
- Triggers on push/PR to `main`, `develop`, `feature/**`
- Runs on Python 3.10, 3.11, 3.12
- Skips LLM tests by default (use `workflow_dispatch` to run manually)
- Generates coverage report
- Uploads to Codecov
- Comments PR with coverage stats

### PR Checks

All PRs must pass:
1. ✅ All tests passing
2. ✅ Coverage thresholds met (Frontend: 60%, Backend: 55%)
3. ✅ No coverage regression

## Coverage Goals

### Short-term (Current)
- **Frontend:** 60% coverage
  - Utilities: 90%+
  - API Service: 80%+
  - Composables: 75%+
  - Components: 50%+

- **Backend:** 55% coverage
  - Core Services: 70%+
  - Agents: 60%+
  - API Endpoints: 65%+
  - Auxiliary Services: 40%+

### Mid-term (1 month)
- **Frontend:** 70% coverage
- **Backend:** 65% coverage

### Long-term (3 months)
- **Frontend:** 80% coverage
- **Backend:** 75% coverage

## Best Practices

### Frontend

1. **Use MSW for API mocking** - Don't mock fetch directly
2. **Test user interactions** - Use `@testing-library/vue` utilities
3. **Mock external dependencies** - Router, stores, etc.
4. **Test error states** - Not just happy paths
5. **Keep tests focused** - One concept per test

### Backend

1. **Use fixtures** - Share common test data via `conftest.py`
2. **Mock external services** - LLM, OSS, image generation
3. **Use in-memory database** - For fast, isolated tests
4. **Mark expensive tests** - Use `@pytest.mark.llm` for API calls
5. **Test edge cases** - Empty inputs, errors, timeouts

## Troubleshooting

### Frontend

**Tests fail with "Cannot find module"**
```bash
# Clear cache and reinstall
rm -rf node_modules package-lock.json
npm install
```

**Coverage not generated**
```bash
# Install coverage provider
npm install -D @vitest/coverage-v8
```

### Backend

**Import errors**
```bash
# Set PYTHONPATH
export PYTHONPATH=/path/to/backend:$PYTHONPATH
pytest
```

**Database locked errors**
```bash
# Use in-memory database for tests
pytest  # conftest.py already configures this
```

## Contributing

When adding new features:

1. **Write tests first** (TDD approach recommended)
2. **Maintain coverage** - Don't decrease overall coverage
3. **Follow naming conventions** - `test_*.py` or `*.test.ts`
4. **Document complex tests** - Add docstrings/comments
5. **Run tests locally** - Before pushing

## Resources

- [Vitest Documentation](https://vitest.dev/)
- [Vue Test Utils](https://test-utils.vuejs.org/)
- [pytest Documentation](https://docs.pytest.org/)
- [MSW Documentation](https://mswjs.io/)
- [Codecov Documentation](https://docs.codecov.com/)

---

**Last Updated:** 2026-02-07
**Maintained by:** VibeBlog Team
