# ragkit User Guide

ragkit is a RAG platform for uploading documents and searching them with natural language. All features are accessible through the admin UI at http://localhost:5173.

---

## Table of Contents

1. [Login](#1-login)
2. [Uploading a Document](#2-uploading-a-document)
3. [Document List and Status](#3-document-list-and-status)
4. [Document Detail and Management](#4-document-detail-and-management)
5. [Search](#5-search)
6. [Document Status Reference](#6-document-status-reference)
7. [Supported File Formats](#7-supported-file-formats)

---

## 1. Login

Open the admin UI and sign in with the email and password provided by your administrator.

---

## 2. Uploading a Document

Use the Upload form at the top of the **Documents** page.

| Field | Description |
| ----- | ----------- |
| Title | A name to identify the document (required) |
| File | The file to upload (required) |
| Description | Additional notes about the document (optional) |

Click **Upload** to start processing: the file is saved, text is extracted, embeddings are generated, and vectors are stored. A success notification appears in the top-right corner when complete.

> **When upload fails**
> - If the embedding service (Ollama) is not running, an error notification is shown. Start Ollama and try again.
> - Files from which no text can be extracted (e.g. scanned image PDFs) will fail to upload.

---

## 3. Document List and Status

Uploaded documents appear in the list on the **Documents** page.

- Type a keyword in the search box to filter by title.
- The **Status** column shows the indexing state. Only documents with `indexed` status are searchable.

---

## 4. Document Detail and Management

Click a document title to open its detail page.

### Preview

Click **Preview** to view PDF and text files directly in the browser.

### Download

Click **Download** to save the original file.

### Replace File

To swap in a new file, select it in the **Replace file** section and click **Replace and re-index**. Existing vectors are deleted and the document is re-indexed from the new file.

### Delete

Click **Delete** to permanently remove the document and all associated data (file and vectors). This action cannot be undone.

---

## 5. Search

Use the **Search** page to query your documents in natural language.

| Field | Description |
| ----- | ----------- |
| Query | What you want to find, in natural language (required) |
| Top K | Maximum number of results to return (default 5, max 50) |
| Document ID | Restrict the search to a specific document (optional) |

Results are shown as text chunks with a relevance score. Click the document title on any result to go to that document's detail page.

> Only documents with `indexed` status appear in search results.

---

## 6. Document Status Reference

| Status | Meaning |
| ------ | ------- |
| `pending` | File saved, waiting to be indexed |
| `chunking` | Splitting text into chunks |
| `embedding` | Generating vector embeddings |
| `indexed` | Indexing complete, available for search |
| `failed` | Indexing failed — see the error message on the detail page |

---

## 7. Supported File Formats

| Format | Extensions |
| ------ | ---------- |
| PDF | `.pdf` |
| Word | `.docx`, `.doc` |
| PowerPoint | `.pptx`, `.ppt` |
| Excel | `.xlsx`, `.xls` |
| Text | `.txt`, `.md`, `.markdown`, `.rst`, `.log` |

Files with other extensions are treated as plain text. If the file cannot be read as text, the upload will fail.
