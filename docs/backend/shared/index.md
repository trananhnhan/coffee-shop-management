---
file_type: index
scope: shared
last_verified: 2026-07-18
---
`docs/backend/shared/index.md`

# Shared — Index

Files under `shared/` apply **project-wide across all backend domains**. Every domain `depends_on` at least one file here.

| File | Content | When to read |
|------|---------|---------------|
| [conventions.md](./conventions.md) | naming, response format, HTTP status codes, base model fields | always, for every backend task |
| [permissions.md](./permissions.md) | role & permission pattern, base permission classes | when building a ViewSet with access control |
| [pagination.md](./pagination.md) | standard pagination pattern | when building a list endpoint |
| [exceptions.md](./exceptions.md) | shared custom exception classes | when raising a business logic error |
| [glossary.md](./glossary.md) | domain-specific terminology | when encountering an unfamiliar field or concept |

## Related
- [Project Docs Index](../../index.md)