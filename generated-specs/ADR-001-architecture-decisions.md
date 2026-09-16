# ADR 001: Architecture Decisions for Autenticación JWT y Serialización Transaccional en Django REST Framework

## Status
Accepted

## Context
Project requiring structured implementation matching Gherkin specification.

## Decisions
- **Architecture Style**: Monolith Architecture (MVC / Monolithic) (monolith)
- **Primary Backend Language**: python
- **Backend Framework**: django (Python 3.11+)
- **ORM / Persistence**: sqlalchemy (SQLAlchemy^2.0.0)
- **Validation**: pydantic (pydantic^2.6.0)
- **Authentication**: jwt-bcrypt (bcrypt cost factor 12, JWT TTL 3600s)
- **Backend Testing Framework**: pytest (pytest^8.0.0, pytest-asyncio)
- **Frontend Framework**: react
- **Frontend Language**: javascript
- **Frontend Bundler**: vite
- **Frontend Unit Testing**: vitest
- **Frontend E2E Testing**: cypress

## Prohibited Layer Dependencies
Domain core must NOT import:
- `direct SQL string interpolation`
- `global state mutation`
- `django`
- `fastapi`
- `flask`
- `eval()`
