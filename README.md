# MCP Starter for Puch AI — URL → Structured Notes

This MCP server provides high-utility web page tools for Puch AI: clean extraction to Markdown, fast summaries with citations, outlines, and batch study guides. It also includes example extras (Job Finder, Image B/W) from the starter.

## What is MCP?

MCP (Model Context Protocol) allows AI assistants like Puch to connect to external tools and data sources safely. Think of it like giving your AI extra superpowers without compromising security.

## What's Included

### 📚 URL → Structured Notes (Primary)
- Cleanly extract web pages into Markdown with metadata and links
- Summarize pages into concise bullet points with citations
- Generate outlines for study/navigation
- Batch summarize multiple URLs into a single study guide

Exposed tools:
- `fetch_notes(url) -> string`
- `summarize_url(url, length="short|medium|long") -> string`
- `outline_url(url) -> string`
- `batch_summarize(urls: string[], length="short|medium|long") -> string`

### ✨ Extras (from starter)
- 🎯 Job Finder (demo): analyze, fetch, and search job postings
- 🖼️ Image Processing: convert an image to black & white

### 🔐 Built-in Authentication
- Bearer token authentication (required by Puch AI)
- Validation tool that returns your phone number

## Quick Setup Guide

### Step 1: Install Dependencies

First, make sure you have Python 3.11 or higher installed. Then:

```bash
# Create virtual environment
uv venv

# Install all required packages
uv sync

# Activate the environment
source .venv/bin/activate
```

### Step 2: Set Up Environment Variables

Create a `.env` file in the project root:

```bash
# Copy the example file
cp .env.example .env
```

Then edit `.env` and add your details:

```env
AUTH_TOKEN=your_secret_token_here
MY_NUMBER=919876543210
```

**Important Notes:**
- `AUTH_TOKEN`: This is your secret token for authentication. Keep it safe!
- `MY_NUMBER`: Your WhatsApp number in format `{country_code}{number}` (e.g., `919876543210` for +91-9876543210)

### Step 3: Run the Server

```bash
cd mcp-bearer-token
python mcp_starter.py
```

You'll see: `🚀 Starting MCP server on http://0.0.0.0:8086`

### Step 4: Make It Public (Required by Puch)

Since Puch needs to access your server over HTTPS, you need to expose your local server:

#### Option A: Using ngrok (Recommended)

1. **Install ngrok:**
   Download from https://ngrok.com/download

2. **Get your authtoken:**
   - Go to https://dashboard.ngrok.com/get-started/your-authtoken
   - Copy your authtoken
   - Run: `ngrok config add-authtoken YOUR_AUTHTOKEN`

3. **Start the tunnel:**
   ```bash
   ngrok http 8086
   ```

#### Option B: Deploy to Cloud

You can also deploy this to services like:
- Railway
- Render
- Heroku
- DigitalOcean App Platform

## How to Connect with Puch AI

1. **[Open Puch AI](https://wa.me/+919998881729)** in your browser
2. **Start a new conversation**
3. **Use the connect command (note trailing slash):**
   ```
   /mcp connect https://your-domain.ngrok.app/mcp/ your_secret_token_here
   ```

4. **List tools and call**
    - `/mcp tools`
    - Then call a tool as guided by Puch. If direct calling is supported in your build:
       - `/mcp call summarize_url {"url":"https://example.com","length":"short"}`
       - In some builds use: `/mcp tools call summarize_url {...}`

## Local testing with curl (JSON-RPC)

The MCP HTTP endpoint expects a trailing slash and an Accept header including both JSON and SSE. Use your AUTH_TOKEN from `.env`.

List tools:
```bash
curl -sS -X POST http://localhost:8086/mcp/ \
   -H "Content-Type: application/json" \
   -H "Accept: application/json, text/event-stream" \
   -H "Authorization: Bearer YOUR_TOKEN" \
   -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

Fetch notes:
```bash
curl -sS -X POST http://localhost:8086/mcp/ \
   -H "Content-Type: application/json" \
   -H "Accept: application/json, text/event-stream" \
   -H "Authorization: Bearer YOUR_TOKEN" \
   -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"fetch_notes","arguments":{"url":"https://www.python.org"}}}'
```

Summarize URL:
```bash
curl -sS -X POST http://localhost:8086/mcp/ \
   -H "Content-Type: application/json" \
   -H "Accept: application/json, text/event-stream" \
   -H "Authorization: Bearer YOUR_TOKEN" \
   -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"summarize_url","arguments":{"url":"https://www.python.org","length":"short"}}}'
```

Outline URL:
```bash
curl -sS -X POST http://localhost:8086/mcp/ \
   -H "Content-Type: application/json" \
   -H "Accept: application/json, text/event-stream" \
   -H "Authorization: Bearer YOUR_TOKEN" \
   -d '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"outline_url","arguments":{"url":"https://developer.mozilla.org/en-US/docs/Web/JavaScript"}}}'
```

Batch summarize:
```bash
curl -sS -X POST http://localhost:8086/mcp/ \
   -H "Content-Type: application/json" \
   -H "Accept: application/json, text/event-stream" \
   -H "Authorization: Bearer YOUR_TOKEN" \
   -d '{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"batch_summarize","arguments":{"urls":["https://www.python.org","https://www.djangoproject.com"],"length":"short"}}}'
```

### Debug Mode

To get more detailed error messages:

```
/mcp diagnostics-level debug
```

### Troubleshooting

- 307 Temporary Redirect → Add trailing slash and POST to `/mcp/`.
- Not Acceptable → Add header `Accept: application/json, text/event-stream`.
- 401 Unauthorized → Check `AUTH_TOKEN` in `.env` and your Authorization header.
- Non-HTML URL → The tools only handle HTML pages; PDFs and others will error.

## Customizing the Starter

### Adding New Tools

1. **Create a new tool function:**
   ```python
   @mcp.tool(description="Your tool description")
   async def your_tool_name(
       parameter: Annotated[str, Field(description="Parameter description")]
   ) -> str:
       # Your tool logic here
       return "Tool result"
   ```

2. **Add required imports** if needed


## 📚 **Additional Documentation Resources**

### **Official Puch AI MCP Documentation**
- **Main Documentation**: https://puch.ai/mcp
- **Protocol Compatibility**: Core MCP specification with Bearer & OAuth support
- **Command Reference**: Complete MCP command documentation
- **Server Requirements**: Tool registration, validation, HTTPS requirements

### **Technical Specifications**
- **JSON-RPC 2.0 Specification**: https://www.jsonrpc.org/specification (for error handling)
- **MCP Protocol**: Core protocol messages, tool definitions, authentication

### **Supported vs Unsupported Features**

**✓ Supported:**
- Core protocol messages
- Tool definitions and calls
- Authentication (Bearer & OAuth)
- Error handling

**✗ Not Supported:**
- Videos extension
- Resources extension
- Prompts extension

## Getting Help

- **Join Puch AI Discord:** https://discord.gg/VMCnMvYx
- **Check Puch AI MCP docs:** https://puch.ai/mcp
- **Puch WhatsApp Number:** +91 99988 81729

---

**Happy coding! 🚀**

Use the hashtag `#BuildWithPuch` in your posts about your MCP!

This starter makes it easy to ship a useful MCP server for Puch AI. Follow setup and start summarizing links with citations in minutes.
