# Day 11 — Login page and the session operator in the UI

> The cookie session from Day 9 was API-only. This day puts a login page in front of the console and shows who is signed in.
>
> Previous: [PLAN_DAY10.md](PLAN_DAY10.md). Next: [PLAN_DAY12.md](PLAN_DAY12.md). Charter: [README.md](README.md).

**Status:** done. The original brief was never written. This page only records what is in the repo.

Day 9 already required a session for ticket and HITL routes. The console now has a page for that session.

- [`frontend/src/pages/LoginPage.tsx`](../frontend/src/pages/LoginPage.tsx) posts email and password. A 401 shows “Invalid email or password”. An already signed-in operator is sent to `/`.
- [`frontend/src/auth/AuthContext.tsx`](../frontend/src/auth/AuthContext.tsx) calls `GET /auth/me` on load and keeps the operator in memory. The cookie stays `HttpOnly`.
- [`frontend/src/auth/RequireAuth.tsx`](../frontend/src/auth/RequireAuth.tsx) holds the console until that check finishes, then sends an anonymous visitor to `/login`.
- [`frontend/src/main.tsx`](../frontend/src/main.tsx) mounts `/login` in the open and `/` behind the guard.
- [`frontend/src/components/AppHeader.tsx`](../frontend/src/components/AppHeader.tsx) shows `display_name` and email, and signs out from the menu. The review still stores `operator.id`, not the display name.

How to run it: [`frontend/README.md`](../frontend/README.md).
