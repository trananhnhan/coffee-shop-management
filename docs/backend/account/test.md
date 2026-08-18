---
domain: accounts
covers: [Branch, User]
status: draft
---

# Test Plan: Accounts Domain

## Part 1 — Unit-level tests (Model / Serializer / View, tested separately)

| Target | Model/File | Case | Input | Expected | Note |
|---|---|---|---|---|---|
| model | Branch | required fields | create without `table_capacity` | error (not null) | |
| model | User | `role` outside choices | role = "invalid" | error on full_clean() | |
| model | User | `branch` nullable | create user without branch | OK (e.g. Owner has no branch) | |
| model | User | FK `branch` PROTECT | delete Branch with users attached | raise ProtectedError | |
| model | User | inherited AbstractUser fields | duplicate username | error (unique, from AbstractUser) | |
| serializer | List/RetrieveBranchSerializer | all fields readonly | attempt write via these serializers | no-op / not used for write | sanity check only |
| serializer | CreateBranchSerializer | missing required field | no `table_capacity` | 400 | |
| serializer | PartialUpdateBranchSerializer | valid partial update | update only `phone` | only `phone` changes | |
| serializer | CreateUserSerializer | password hashing | create with plain password | stored password is hashed, not plaintext | |
| serializer | CreateUserSerializer | StoreManager creates user | request_user = StoreManager, branch omitted in payload | `branch` forced to request_user.branch regardless of payload | **security-critical** |
| serializer | CreateUserSerializer | StoreManager assigns invalid role | request_user = StoreManager, role = STORE_MANAGER | ValidationError `{"detail":...}` | privilege escalation guard |
| serializer | CreateUserSerializer | StoreManager assigns valid role | role = CASHIER or KITCHEN | created successfully | |
| serializer | CreateUserSerializer | Owner creates staff without branch | request_user = Owner, role = CASHIER, branch not provided | ValidationError `{"detail":...}` | |
| serializer | CreateUserSerializer | Owner creates another Owner | role = OWNER, branch not provided | passes validation (branch not required for OWNER) | intentional: Owner is not tied to any branch |
| serializer | CreateUserSerializer | StoreManager tries to set branch explicitly in payload | payload includes `branch=<other_branch>` | still overwritten to request_user.branch | confirms server-side override, not trusting client input |
| serializer | PartialUpdateUserSerializer | StoreManager changes branch | data includes different branch | ValidationError `{"detail":...}` | |
| serializer | PartialUpdateUserSerializer | StoreManager promotes to manager | role = STORE_MANAGER | ValidationError `{"detail":...}` | privilege escalation guard |
| serializer | PartialUpdateUserSerializer | StoreManager valid update | role = KITCHEN (switching within allowed roles) | succeeds | |
| serializer | PartialUpdateUserSerializer | password update | payload includes password | stored password is hashed | |
| serializer | PartialUpdateUserSerializer | Owner changes branch/role | any value | not restricted (validate() only checks StoreManager) | confirm Owner has no extra restriction here |
| view | BranchViewSet | permission | role != Owner | 403 | |
| view | BranchViewSet | is_active filter | ?is_active=false | queryset filtered correctly | |
| view | BranchViewSet | activate/deactivate idempotency guard | activate an already-active branch, or deactivate an already-inactive one | 400 `{"detail": "... is already active/inactive."}` | via `BaseModel.activate()/deactivate()` raising ValueError |
| view | BranchViewSet | http methods | DELETE request | 405 | |
| view | UserViewSet | permission list/create/retrieve | role not Owner/StoreManager | 403 | |
| view | UserViewSet | permission list/create/retrieve | Cashier/Kitchen calls list | 403, blocked by `IsOwnerOrStoreManager.has_permission()` before queryset even runs | confirms queryset's `.none()` branch is effectively dead code for these roles via this endpoint |
| view | UserViewSet | object permission partial_update | StoreManager targets a Cashier/Kitchen in own branch | allowed (CanManageTargetUser passes) | |
| view | UserViewSet | object permission partial_update | StoreManager targets another StoreManager | 403 (`obj.role` not in [CASHIER, KITCHEN]) | |
| view | UserViewSet | object permission partial_update | StoreManager targets an Owner | 403 | |
| view | UserViewSet | object permission partial_update | StoreManager targets **themselves** | 403 — `obj.role == STORE_MANAGER`, not in allowed list | StoreManager cannot self-update via this endpoint at all, not even their own password |
| view | UserViewSet | object permission partial_update | Owner targets any user (including another Owner) | allowed (Owner bypasses object check) | |
| view | UserViewSet | queryset Owner | Owner lists users | sees all, is_active filter works | |
| view | UserViewSet | activate/deactivate idempotency guard | activate an already-active user, or deactivate an already-inactive one | 400 `{"detail": "... is already active/inactive."}` | applies after `CanManageTargetUser` passes — test with a valid target, not a permission-blocked one |
| view | UserViewSet | queryset StoreManager | StoreManager lists users | only sees active users in own branch | |
| view | UserViewSet.me | any authenticated user | GET /me | returns own user data | GET only — no PATCH, so `me` cannot be used to self-update password either |

---

## Part 2 — Integration / Flow tests

| Flow | Steps | Expected | Role per step | Note |
|---|---|---|---|---|
| StoreManager onboards staff | StoreManager creates a Cashier user via API | User created, branch forced to StoreManager's branch, role=CASHIER | StoreManager | |
| StoreManager privilege escalation attempt | StoreManager tries to create a user with role=STORE_MANAGER or branch=other_branch | 400 `{"detail":...}`, no user created | StoreManager | security-critical, test both role and branch vectors |
| Owner creates full staff hierarchy | Owner creates Branch → Owner creates StoreManager for that branch → StoreManager creates Cashier | All succeed with correct branch/role chain | Owner → Owner → StoreManager | |
| Cross-branch management blocked | StoreManager (branch A) tries partial_update on a Cashier in branch B | 404 first — `get_queryset()` already filters StoreManager's visible users to `branch=user.branch`, so the object is never found; `CanManageTargetUser` never even runs | StoreManager | blocked at queryset layer, not the object-permission layer |
| Deactivated user re-appears for Owner only | Owner deactivates a user → StoreManager lists users → Owner lists with is_active=false | StoreManager no longer sees the user; Owner can still retrieve it with the filter | Owner → StoreManager → Owner | |
| No self-service password change exists | Cashier/Kitchen/StoreManager all attempt to change their own password via any endpoint | All blocked: non-Owner/StoreManager roles fail `IsOwnerOrStoreManager` on partial_update; StoreManager targeting self fails `CanManageTargetUser`; `/me` is GET-only | Cashier, Kitchen, StoreManager | worth flagging to the team as a product gap, not just a test case — currently only Owner can change a StoreManager's password, and only via targeting that StoreManager as an object |

---

## Known issues / things to watch for
- **No self-service password change path exists** for Cashier, Kitchen, or StoreManager (see integration flow above). Only Owner can change a StoreManager's password; only Owner/StoreManager can change a Cashier/Kitchen's password. This may be intentional (admin-managed credentials) but is worth confirming with the product requirements rather than assuming it's a bug — either way it needs an explicit test asserting the current (locked-down) behavior so it doesn't silently change later.
- `CreateUserSerializer.validate()`: Owner creating another OWNER skips the "branch required" check — confirmed intentional, Owner is not tied to any branch.
- `IsOwnerOrStoreManager.has_permission()` runs before `get_queryset()` in DRF's request cycle, so `UserViewSet.get_queryset()`'s `User.objects.none()` branch for non-Owner/StoreManager roles is unreachable through this viewset — that branch only matters if the queryset method is reused elsewhere.
- `CanManageTargetUser` is object-level only (no `has_permission` override, defaults to True) — it only fires once an object is fetched. Combined with `get_queryset()` already scoping StoreManager to their own branch, a cross-branch object access is blocked earlier (404) than the role check (403) would suggest — test should assert 404, not 403, for that case.