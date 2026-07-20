# Frontend Deploy Runbook

## Overview

This runbook covers deployment, configuration, failure handling, and incident response for the IA-Investing Next.js frontend application.

---

## Auth Failure Handling

### OIDC Refresh Flow

1. User authenticates via SSO → NextAuth/Next.js API route issues session cookie.
2. Session cookie is httpOnly, SameSite=Lax, secure in production.
3. On each page load, the frontend calls `/api/auth/session` to validate the session.
4. When the session expires, the API returns 401 → frontend redirects to `/login`.
5. Refresh tokens (if configured) attempt silent renewal before expiry.

### Cookie Expiry

- Default session duration: 24 hours (configurable via `NEXTAUTH_SESSION_MAX_AGE`).
- On expiry, all protected routes redirect to `/login`.
- Users are never silently logged out mid-action; redirects happen on navigation or refetch.

### Redirect Behavior

| Condition | Behavior |
|-----------|----------|
| No session cookie | Redirect to `/login` |
| Session expired (401) | Redirect to `/login` |
| Invalid session (400) | Redirect to `/login` |
| Backend 403 | Show error panel, no redirect |

---

## SSE Failure Handling

### Reconnection Strategy

The SSE client implements exponential backoff:

1. Initial reconnect attempt: 1 second
2. Max reconnect attempts: 10
3. Backoff formula: `min(1000 * 2^attempt, 30000)` ms
4. After max attempts, falls back to polling every 30 seconds

### Stale Data Detection

- Each SSE event carries a timestamp; if no event received for >5 minutes, data is marked `stale`.
- `StaleWarning` banner appears across affected pages.
- Users can manually trigger a refresh via the UI or browser reload.

### Manual Refresh

- Click "Refresh" button on affected pages.
- Use browser hard reload (Ctrl+Shift+R) to reset SSE connection.
- Check browser DevTools → Network → EventSource for connection status.

---

## Feature Flags

### NEXT_PUBLIC_ENABLE_DEMO_DATA

- **Type**: `boolean`
- **Default**: `true` in development, `false` in production
- **Purpose**: When enabled, the frontend uses mock/demo data instead of calling the backend API.
- **Toggle**: Set in `.env.local` or Vercel environment variables.
- **Impact**: All hooks (`usePortfolios`, `useAgentRuns`, etc.) return demo data. No backend required.

### Other Flags

| Flag | Purpose |
|------|---------|
| `NEXT_PUBLIC_API_URL` | Backend API base URL |
| `NEXT_PUBLIC_AUTH_URL` | NextAuth base URL |
| `NEXT_PUBLIC_SENTRY_DSN` | Error tracking endpoint |

---

## Dependency Failures

### Backend API Down

When the backend API is unreachable:

1. **Graceful degradation**: Pages render with `DataStatePanel` in error/empty state.
2. **No crashes**: React error boundaries prevent white screens.
3. **User messaging**: Each page shows context-appropriate error messages.
4. **Retry logic**: TanStack Query retries 3 times with exponential backoff.
5. **Cache fallback**: Stale cached data is served when available.

### Database Down

- Same behavior as backend API down; the frontend cannot fetch data.
- Pages display `DataStatePanel` with `state="error"`.

### Auth Provider Down

- SSO button redirects to `/api/auth/login` which returns 502/503.
- Login page shows the SSO button; users can retry.

---

## Rollback Procedure

### Git-Based Rollback

```bash
# 1. Identify the commit to revert to
git log --oneline -10

# 2. Revert the problematic commit
git revert <commit-hash>

# 3. Push to trigger CI/CD
git push origin main

# 4. Verify deployment
curl -I https://your-domain.com
```

### Vercel Rollback

```bash
# List recent deployments
vercel ls

# Promote a previous deployment
vercel promote <deployment-url>
```

### Manual Rollback

1. Check out the last known good commit: `git checkout <good-commit>`
2. Build: `npm run build`
3. Deploy the `.next` output to hosting
4. Verify: `curl -I https://your-domain.com`

---

## Incident Response

### When UI is Broken

**Checklist:**

1. **Check build status**: `npm run build` locally. If it fails, the issue is in the code.
2. **Check API proxy**: Verify `/api/backend/` routes return data.
3. **Check auth cookies**: Open DevTools → Application → Cookies. Verify session cookie exists.
4. **Check network**: DevTools → Network tab. Look for 4xx/5xx responses.
5. **Check console**: DevTools → Console. Look for JavaScript errors.
6. **Check deployment**: Vercel dashboard → Deployments. Is the latest deploy healthy?
7. **Check environment variables**: Verify `NEXT_PUBLIC_*` vars are set correctly.

### Common Issues

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| White screen | JS bundle error or missing env var | Check build logs, verify env vars |
| Redirect loop | Auth misconfiguration | Check `NEXTAUTH_URL` and cookie settings |
| 502 on API routes | Backend down | Check backend health, restart if needed |
| Stale data | SSE connection lost | Refresh page, check SSE endpoint |
| Missing features | Feature flag disabled | Check `NEXT_PUBLIC_ENABLE_DEMO_DATA` |

### Post-Incident

1. Document the incident in the audit trail.
2. Create a post-mortem if the outage lasted >15 minutes.
3. Update this runbook with lessons learned.
4. File a bug if the issue was a code defect.

---

## Monitoring

- **Vercel Analytics**: Page load times, Web Vitals
- **Sentry**: JavaScript errors, unhandled exceptions
- **SSE health**: Connection status, reconnect counts
- **API latency**: TanStack Query metrics logged to console in dev

---

## Deployment Checklist

- [ ] `npm run build` passes locally
- [ ] `npm run typecheck` passes
- [ ] `npm run lint` passes
- [ ] `npm test -- --run` all tests pass
- [ ] Environment variables configured in hosting platform
- [ ] Domain DNS configured (if new domain)
- [ ] SSL certificate active
- [ ] Auth provider (OIDC) configured for production
- [ ] Backend API URL configured and reachable
- [ ] Feature flags set correctly for production
