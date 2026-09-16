# 🚀 AI AGENT MASTER IMPLEMENTATION PROMPT
## Feature: Autenticación JWT y Serialización Transaccional en Django REST Framework (Spec Hash: 29873150)
## Architecture: MONOLITH | Stack: PYTHON (django)
## Prompt Version / Audit Hash: prt_a9d40f7b
## Author / Developer: Fenner Eduardo González C. <fennereduardo@gmail.com> (source: git)

### 📌 Context Files to Read & Follow:
- @.ghkgovernance.yaml
- @features/django_drf_transaction.feature
- @generated-specs/autenticacinjwtyserializacintransaccionalendjangorestframework.contract.py
- @generated-specs/ADR-001-architecture-decisions.md
- @generated-specs/openapi.json
- @generated-specs/docker-compose.yml

### 🛠️ Technical Guardrails & Stack Specifications:
- **Language**: python (django)
- **Persistence**: sqlalchemy + mysql
- **Validation**: pydantic
- **Testing Framework**: pytest

### 🐳 Docker Execution Sandbox & Host Isolation Guardrails:
> **IMPORTANT**: If your host operating system lacks the native runtime SDK (PYTHON), DO NOT install heavy packages directly on the host machine.
> Execute all compilation, migrations, and test runs inside the isolated Docker container:
> 
> ```bash
> # Start database and infrastructure services
> docker compose up -d
> 
> # Execute test suite inside Docker sandbox container:
> docker compose run --rm app pytest
> ```

### 🎯 Mandatory Step-by-Step Implementation Flow:

#### Phase 1: Pure Domain Layer
1. Read the feature specification in `features/django_drf_transaction.feature` and contract in `generated-specs/autenticacinjwtyserializacintransaccionalendjangorestframework.contract.py`.
2. Implement pure domain Entities, Value Objects, and Domain Events.
3. Ensure zero dependencies on external frameworks or database drivers in the domain core.

#### Phase 2: Application Use Cases & Infrastructure
1. Implement the Repository Port interface using SQLALCHEMY (mysql).
2. Implement Controllers/Handlers to process HTTP requests and return appropriate status codes (e.g. 201 Created, 400 Bad Request).
3. Apply validation using pydantic.

#### Phase 3: Automated Unit & Feature Testing
1. Implement automated test cases in PYTEST matching all scenarios in `features/django_drf_transaction.feature`.
2. Assert HTTP response status codes, payload structures, and event emissions.
3. If host environment lacks SDK, run verification inside Docker sandbox (`docker compose run --rm app pytest`).
4. Ensure 100% scenario pass rate.
