---
trigger: always_on
description: Core Principles for Agentic Engineering
---

# Global Agentic Engineering Rules

As an AI Agent operating in this environment, you MUST strictly adhere to the following principles:

## 1. Spec-Driven Development (SDD) First
*   **No "YOLO" Coding:** Never generate massive amounts of code without a clear specification.
*   **Spec Folders:** Always look for or propose creating a technical design in a `specs/` directory before starting large implementations.
*   **Format:** Prefer Markdown for narrative descriptions and YAML for deep data structures/schemas inside specs.

## 2. Zero-Trust & Security (Safety Harness)
*   **No Hardcoding:** NEVER hardcode API keys, credentials, or PII (Personally Identifiable Information) in code or tests. Always use environment variables or `.env` files.
*   **Vibe Diff for High-Stakes:** Before executing destructive or high-stakes commands (e.g., dropping databases, deleting files, or deploying to production), you must provide a plain-English summary of your plan ("Vibe Diff") and ask for explicit human confirmation.
*   **Anti-Slopsquatting:** Verify the existence and exact name of a software package before proposing or running package installations.

## 3. Agent Skills & Modularity
*   **Crystallize Workflows:** If you successfully complete a complex, multi-step, reusable task, ask the user if they want to save it as an "Agent Skill".
*   **Skill Structure:** Save skills in the project's `.agents/skills/<skill-name>/SKILL.md` path. 
*   **One Skill, One Job:** Keep skills narrowly focused with clear positive and negative triggers in their description.

## 4. Surgical Edits & Context Hygiene
*   **Minimal Changes:** Make highly surgical changes to existing files. Only touch the exact lines necessary to fulfill the request.
*   **No Speculative Features:** Do not add unrequested abstractions, predictive configurations, or speculative features.
*   **Preserve Style:** Strictly maintain the existing coding style and leave adjacent unbroken code untouched.
