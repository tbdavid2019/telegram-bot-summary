---
name: oli-summary-service
description: Summarize YouTube transcripts, web articles, podcasts, or raw text into structured Markdown summaries in Traditional Chinese or English.
---

# Oli Summary Service Integration Skill

Use this skill when you need to summarize content from a YouTube video URL, general web page URL, podcast URL, or raw text.

## API Endpoint Details

*   **Health / Readiness**: `GET /health` (liveness) and `GET /readyz` (MongoDB & bot readiness)
*   **Summarize HTTP Method**: `POST`
*   **Path**: `/api/v1/summarize`
*   **Default Port**: `8001`
*   **Authentication**: Bearer Token (via `API_AUTH_TOKENS` or personal `/apikey` command in Telegram private chat)
    *   **Header**: `Authorization: Bearer <YOUR_API_AUTH_TOKEN>`

## Request Schema

```json
{
  "input": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "language": "zh-TW",
  "user_note": "Optional personal commentary or questions"
}
```

*   `input` (string, required, max 1,000,000 chars): The URL (YouTube, Web, Podcast) or raw text to summarize (also supports inline `URL + user note`).
*   `language` (string, optional): The target language. Defaults to `"zh-TW"`. Supports `"en"`.
*   `model` (string, optional): Specific model override if configured.
*   `user_note` (string, optional, max 4,000 chars): Personal note, commentary, or questions prepended and directly addressed by the LLM.

## Response Schema

```json
{
  "status": "success",
  "title": "AI SEO 優化後標題",
  "original_title": "Rick Astley - Never Gonna Give You Up (Official Music Video)",
  "original_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "summary": "### ⓵ 【容易懂 Easy Know】\n這是一首經典的流行樂曲...\n\n### ⓶ 【總結 Overall Summary】\n...\n",
  "is_ad": false
}
```

*   `status` (string): `"success"` when summarized, or `"hidden"` when flagged as commercial ad/spam by Clef System One.
*   `title` (string): The resolved SEO title of the web page, video, or text.
*   `original_title` (string or null): The raw source title before SEO optimization (if valid and present).
*   `original_url` (string or null): The original URL if one was provided in the request.
*   `summary` (string): The Markdown-formatted summary containing the 7 standard structured sections (`⓵ Easy Know`, `⓶ Overall Summary`, `⓷ Viewpoints`, `⓸ Key Points`, `⓹ 3-Question Quiz`, `💡 Suggested Follow-ups`, `⓺ Hashtags`, plus optional `💬 Response to Your Note & Questions`), or a hidden-ad notice when `status == "hidden"`.
*   `is_ad` (boolean): `true` if flagged as promotional/ad spam by Clef System One.

---

## Instructions for LLM/Agents

1.  **URL Extraction**: Identify if the user has provided a URL. If so, extract the exact URL string (or pass inline URL + note directly).
2.  **Text Extraction**: If the user provides a large chunk of text, pass it directly in the `input` field.
3.  **API Call**: Construct a `POST` request to `https://<API_HOST>/api/v1/summarize` (prefer HTTPS reverse proxy in production; use `http://localhost:8001` only locally) with `Authorization: Bearer <API_AUTH_TOKEN>`.
4.  **Display the Result**: Output the `summary` returned from the API **exactly as Markdown**. Handle `"status": "hidden"` (`"is_ad": true`) gracefully, and handle HTTP `400` (SSRF/extraction error), `401` (invalid token), `422` (validation/input limit), `429` (rate limit), and `503` (LLM/key backend/readiness unavailable).

---

## OpenAPI 3.0 Specification (YAML)
For Custom GPTs or API integrations, copy the configuration below:

```yaml
openapi: 3.0.0
info:
  title: Oli Summary API
  description: Summarize YouTube videos, web content, podcasts, or raw text.
  version: 1.0.0
servers:
  - url: http://localhost:8001
paths:
  /health:
    get:
      summary: Liveness health check
      operationId: healthCheck
      responses:
        '200':
          description: Service is alive
  /readyz:
    get:
      summary: Readiness health check (verifies Telegram bot and MongoDB connectivity)
      operationId: readinessCheck
      responses:
        '200':
          description: Service is ready
        '503':
          description: Bot not ready or MongoDB unreachable
  /api/v1/summarize:
    post:
      summary: Summarize input content
      operationId: summarizeContent
      security:
        - BearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                input:
                  type: string
                  description: YouTube/Web URL or raw text to summarize.
                language:
                  type: string
                  description: Output language (e.g., 'zh-TW', 'en').
                  default: 'zh-TW'
                model:
                  type: string
                  description: Optional model override.
                user_note:
                  type: string
                  description: Optional personal note or questions (max 4000 chars).
              required:
                - input
      responses:
        '200':
          description: Content summarized successfully (or hidden as ad)
          content:
            application/json:
              schema:
                type: object
                properties:
                  status:
                    type: string
                    enum: [success, hidden]
                  title:
                    type: string
                  original_title:
                    type: string
                    nullable: true
                  original_url:
                    type: string
                    nullable: true
                  summary:
                    type: string
                  is_ad:
                    type: boolean
        '400':
          description: Bad Request - SSRF blocked or extraction failure
        '401':
          description: Unauthorized - Invalid or missing token
        '422':
          description: Unprocessable Entity - Missing or oversized request payload (max 200,000 chars)
        '429':
          description: Too Many Requests - Per-owner or pre-auth rate limit exceeded
        '503':
          description: Service Unavailable - Bot not ready, concurrency busy, or LLM/key backend unavailable
components:
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
```
