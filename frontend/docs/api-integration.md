# Frontend API Integration Guide

## Base URL
- Default local backend base URL: `http://127.0.0.1:8000`
- Frontend override env var: `VITE_API_BASE_URL`

Example (`frontend/.env.local`):
```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
```

## Endpoint Overview

### 1) Health Check
- `GET /api/health`
- Purpose: confirm service readiness.

Example response:
```json
{
  "status": "ok",
  "app_name": "QuarkAgent Web API",
  "version": "0.1.0",
  "timestamp": "2026-02-27T03:00:00+00:00"
}
```

### 2) Create Session
- `POST /api/sessions`
- Purpose: create a single in-memory chat session.

Example response:
```json
{
  "session_id": "e8f4b8cbac50417abf34f6e3d4f9f741",
  "created_at": "2026-02-27T03:00:00+00:00",
  "expires_at": "2026-02-27T03:30:00+00:00"
}
```

### 3) Delete Session
- `DELETE /api/sessions/{session_id}`

Example response:
```json
{
  "session_id": "e8f4b8cbac50417abf34f6e3d4f9f741",
  "deleted": true
}
```

### 4) List Available Tools
- `GET /api/tools`

Example response:
```json
{
  "tools": ["read", "write", "bash", "calculator"]
}
```

### 5) Sync Chat
- `POST /api/chat`
- Body:
```json
{
  "session_id": "e8f4b8cbac50417abf34f6e3d4f9f741",
  "message": "Summarize current project structure",
  "max_iterations": 10
}
```
- Returns full answer + captured events.

### 6) Streaming Chat (SSE)
- `POST /api/chat/stream`
- Body same as `/api/chat`
- Header: `Accept: text/event-stream`

## SSE Event Contract
Server emits events in this set:
- `status`
- `tool_start`
- `tool_end`
- `final`
- `error`
- `done`

SSE frame format:
```text
event: status
data: {"type":"status","timestamp":"...","data":{"message":"Thinking..."}}
```

Event payload shape:
```json
{
  "type": "status",
  "timestamp": "2026-02-27T03:00:00+00:00",
  "data": {
    "message": "Thinking..."
  }
}
```

## Frontend Handling Rules
- Append every event to timeline panel.
- For `final`: render `data.answer` as assistant message.
- For `error`: show top-level error banner and keep timeline.
- For `done`: switch UI state back to idle.

## Error Handling
- `404`: session missing/expired, recreate session and retry.
- `422`: request schema validation failed.
- `500`: server/runtime or model call error.

## OpenAPI Docs
- Backend auto docs: `/docs`
- Redoc: `/redoc`
