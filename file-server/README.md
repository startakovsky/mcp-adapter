# MCP File Server

A minimal MCP server for file storage and retrieval, designed for use in the MCP Adapter ecosystem. Exposes file management tools (upload, download, delete) via the MCP protocol for seamless integration with the gateway and other services.

## Features
- Upload files (returns a file_id)
- Download files by file_id
- Delete files by file_id
- List files (optional, for debugging)

## Usage

This service is intended to be used programmatically via MCP tool calls, not as a direct REST API.

### Quick Start (Docker Compose)

This service is included in the main `docker-compose.yml` for MCP Adapter. To start all services:

```bash
docker-compose up -d
```

### Build and Run Manually

```bash
docker build -t mcp-file-server .
docker run --rm -p 8003:8000 -v $(pwd)/shared_files:/app/shared_files mcp-file-server
```

### API

- **upload_file**: Upload a file (returns file_id)
- **get_file_url**: Get a download URL for a file
- **delete_file**: Delete a file by file_id

All files are stored in a shared Docker volume, configurable via the `SHARED_FILES_PATH` environment variable.

## Health Check

```bash
curl http://localhost:8003/health
```

## Info

```bash
curl http://localhost:8003/info
```
