# Testing Plan

## Overview
We need to add a testing strategy to ensure changes don't break existing functionality. Since this is a Python web application using `nicegui` and `sqlite`, we can approach testing in a few layers.

## Proposed Strategy

1.  **Testing Framework**: 
    - Use `pytest` as our primary testing framework. It's the standard in the Python ecosystem and works well with `uv`.
    - Add `pytest` and `pytest-asyncio` (if needed for NiceGUI) to our `dev` dependency group.

2.  **Testing Layers**:
    - **Unit Tests (Business Logic)**: Test functions in `src/item_service.py`. We can mock the database calls or use an in-memory SQLite database to ensure the business rules (like avoiding duplicate names, handling empty names) work correctly.
    - **Integration Tests (Database)**: Test functions in `src/database_crud.py`. We should configure these tests to use an in-memory SQLite database (`:memory:`) so they run fast and don't affect our real `list.db`.
    - **UI/E2E Tests (Optional for now, but good to keep in mind)**: Testing the NiceGUI frontend. NiceGUI supports testing using Playwright (`pytest-playwright`), which allows us to simulate clicking buttons and typing text in a headless browser.

3.  **Folder Structure**:
    - Create a `tests/` directory at the root of the project.
    - Inside, create files like `test_item_service.py`, `test_database_crud.py`, etc.

4.  **Continuous Integration (CI)**:
    - (Future Step) Set up GitHub Actions or similar to run these tests automatically whenever we push code.

## Progress / Next Steps
- [x] Discuss and agree on the testing framework (`pytest`).
- [x] Discuss the scope of our first tests (e.g., should we start with the database, the business logic, or both?).
- [x] Install `pytest` using `uv`.
- [x] Write the first test case (Unit tests for `item_service.py` using mocks).
- [ ] Write integration tests for `database_crud.py` using an in-memory database.
