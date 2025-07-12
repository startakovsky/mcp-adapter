# Hello World MCP Server

A simple example MCP (Model Context Protocol) server demonstrating basic FastMCP usage with uv package management.

## Features

- **greet** - Generate personalized greeting messages
- **echo** - Echo messages with optional modifications
- **server_info** - Get server information and capabilities

## Quick Start

### Development
```bash
# Install dependencies
uv sync

# Run the server
uv run python hello_world.py
```

### Docker
```bash
# Build the container
docker build -t hello-world-mcp .

# Run the container
docker run -p 8000:8000 hello-world-mcp
```

## API Endpoints

- `GET /` - Server information
- `GET /health` - Health check
- `GET /docs` - Interactive API documentation
- `POST /tools/greet` - Generate greeting
- `POST /tools/echo` - Echo message
- `POST /tools/server_info` - Get server details

## Example Usage

```bash
# Health check
curl http://localhost:8000/health

# Generate greeting
curl -X POST http://localhost:8000/tools/greet \
  -H "Content-Type: application/json" \
  -d '{"name": "World", "greeting": "Hello"}'

# Echo message
curl -X POST http://localhost:8000/tools/echo \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello World", "uppercase": true}'
```

## Configuration

Set environment variables in `.env`:

```bash
SERVER_PORT=8000
LOG_LEVEL=INFO
DEBUG=true
```