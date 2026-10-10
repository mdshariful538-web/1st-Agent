# 24/7 Personal AI Agent Architecture

## Overview
A personal AI assistant that operates 24/7 via Telegram. It can perform web research, remember personal context, and run scheduled background tasks even when the local computer is offline.

## System Components

```yaml
Architecture:
  Interface: Telegram Bot API (python-telegram-bot v22.8)
  Brain: Google Gemini API (gemini-2.5-flash)
  Database: SQLite (memory.db)
  Deployment: Dockerized container for Cloud Platform (Render / Railway / Cloud Run)

Core_Skills:
  - name: web_search
    description: Live internet search using duckduckgo-search.
  - name: memory_management
    description: CRUD operations on SQLite for long-term user context.
  - name: task_scheduler
    description: Background job scheduling using APScheduler (e.g., daily briefings).

Security_Guardrails:
  - Authentication: Strict Telegram ALLOWED_USER_ID validation.
  - Secrets_Management: All API keys loaded via .env / cloud secrets.
  - Sandboxing: Execution environment isolated within a Docker container.
```

## Workflow (State > Action > Outcome)
1. **Given** the user sends a message via Telegram.
2. **When** the message requires live data, the Agent invokes the `search_web` tool.
3. **When** the message contains a reminder, the Agent invokes the `schedule_task` tool.
4. **Then** the Agent compiles the tool outputs and sends a formatted Bengali response back to the user.

## Deployment Strategy
To make the agent run 24/7 when the PC is off, the project will be packaged with a `Dockerfile` and `requirements.txt`. It will be deployed to a free/low-cost cloud provider.
