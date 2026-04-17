# Release Checklist

## Pre-Release

- [ ] All tests pass in CI
- [ ] Database migration plan reviewed
- [ ] Security-sensitive changes reviewed by another engineer
- [ ] Release notes drafted

## Deployment Steps

1. Deploy backend API to staging.
2. Run smoke tests for auth, upload, and search.
3. Deploy admin frontend.
4. Monitor logs and metrics for 30 minutes.

## Rollback Strategy

If error rate exceeds threshold:

1. Revert to previous backend image.
2. Restore previous frontend build.
3. Announce rollback status in the team channel.

## Validation Commands

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/docs
```
