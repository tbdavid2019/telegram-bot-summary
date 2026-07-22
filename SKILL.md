---
name: oli-summary-service
description: Summarize YouTube transcripts, web articles, podcasts, or raw text into structured Markdown summaries in Traditional Chinese or English.
---

# Oli Summary Service Integration Skill

Use this skill when you need to summarize content from a YouTube video URL, general web page URL, podcast URL, or raw text.

## API Endpoint Details

*   **HTTP Method**: `POST`
*   **Path**: `/api/v1/summarize`
*   **Default Port**: `8001`
*   **Authentication**: Bearer Token
    *   **Header**: `Authorization: Bearer <YOUR_API_AUTH_TOKEN>`

## Request Schema

```json
{
  "input": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "language": "zh-TW"
}
```

*   `input` (string, required): The URL (YouTube, Web, Podcast) or the raw text content to summarize.
*   `language` (string, optional): The target language. Defaults to `"zh-TW"`. Supports `"en"`.
*   `model` (string, optional): Specific model overrides if configured.

## Response Schema

```json
{
  "status": "success",
  "title": "Rick Astley - Never Gonna Give You Up (Official Music Video)",
  "original_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "summary": "# ⓵ 【容易懂 Easy Know】\n這是一首經典的流行樂曲...\n\n# ⓶ 【總結 Overall Summary】\n...\n"
}
```

*   `status` (string): `"success"` if successful.
*   `title` (string): The resolved title of the web page or video.
*   `original_url` (string or null): The original URL if one was provided in the request.
*   `summary` (string): The rich Markdown-formatted summary containing the 6 standard structured sections.

---

## Instructions for LLM/Agents

1.  **URL Extraction**: Identify if the user has provided a URL. If so, extract the exact URL string.
2.  **Text Extraction**: If the user provides a large chunk of text, pass it directly in the `input` field.
3.  **API Call**: Construct a `POST` request to `http://<API_HOST>:8001/api/v1/summarize`. Include the authentication header: `Authorization: Bearer <API_AUTH_TOKEN>`.
4.  **Display the Result**: Output the `summary` returned from the API **exactly as Markdown**. Do not alter the structure of the 6 sections. Include the `title` and `original_url` if applicable at the top or bottom of your response.

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
              required:
                - input
      responses:
        '200':
          description: Content summarized successfully
          content:
            application/json:
              schema:
                type: object
                properties:
                  status:
                    type: string
                  title:
                    type: string
                  original_url:
                    type: string
                    nullable: true
                  summary:
                    type: string
        '401':
          description: Unauthorized - Invalid or missing token
        '400':
          description: Bad Request - Missing input or extraction failure
components:
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
```
