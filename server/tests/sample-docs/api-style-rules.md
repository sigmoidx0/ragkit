# API Style Rules

## Naming

- Use plural nouns for collection endpoints (`/documents`, `/users`).
- Use kebab-case for URL path segments.
- Keep JSON field names in snake_case for consistency with backend models.

## Error Response Format

All API errors should return this structure:

```json
{
  "error": {
    "code": "invalid_request",
    "message": "A clear explanation for users."
  }
}
```

## Authentication

- Private endpoints require `Authorization: Bearer <token>`.
- Tokens expire after a configured TTL.
- Avoid embedding secrets in query parameters.

## Pagination

Use `limit` and `offset` parameters for list endpoints.

Example:

`GET /documents?limit=20&offset=40`
