# 📦 Aiko Backend - Complete Project Structure

## Directory Tree

```
aiko-backend/
│
├── 📄 main.py                          # FastAPI application entry point
├── 📄 requirements.txt                 # Python dependencies
├── 📄 .env.template                    # Environment variables template
├── 📄 Dockerfile                       # Docker container configuration
├── 📄 docker-compose.yml               # Docker Compose orchestration
│
├── 📚 README.md                        # Complete documentation
├── 📚 QUICKSTART.md                    # 5-minute quick start guide
├── 📚 FRONTEND_INTEGRATION.md          # Frontend integration examples
├── 📚 AGENTS.md                        # LangGraph agent documentation
│
├── 📁 config/
│   ├── __init__.py
│   └── settings.py                     # Global configuration & environment
│
├── 📁 core/
│   ├── __init__.py
│   ├── llm_factory.py                  # LLM provider factory
│   └── services.py                     # Service manager & initialization
│
├── 📁 agent/
│   ├── __init__.py
│   └── core.py                         # LangGraph AI agent
│
├── 📁 memory/
│   ├── __init__.py
│   └── manager.py                      # ChromaDB + SQLite memory system
│
├── 📁 tools/
│   ├── __init__.py
│   ├── search.py                       # Internet search (Tavily + DDG)
│   ├── filesystem.py                   # Safe file operations
│   ├── document_reader.py              # PDF/Word/TXT reader
│   └── image_analysis.py               # Vision model support
│
├── 📁 voice/
│   ├── __init__.py
│   └── manager.py                      # STT & TTS integration
│
├── 📁 api/
│   ├── __init__.py
│   ├── auth.py                         # API key authentication
│   └── routes/
│       ├── __init__.py
│       ├── chat.py                     # Chat & message endpoints
│       ├── voice.py                    # Voice (TTS/STT) endpoints
│       ├── tools.py                    # Tools (search, fs, etc.) endpoints
│       ├── memory.py                   # Memory management endpoints
│       ├── settings.py                 # Settings & configuration endpoints
│       └── health.py                   # Health check endpoints
│
├── 📁 data/ (created at runtime)
│   ├── chroma/                         # ChromaDB vector database
│   ├── aiko.db                         # SQLite conversation database
│   ├── uploads/                        # User uploads
│   └── documents/                      # User documents
│
├── 📁 logs/ (created at runtime)
│   └── app.log
│
├── 📄 models.py                        # Pydantic data models
├── 📄 utils.py                         # Utility functions & helpers
└── 📄 __init__.py                      # Package initialization
```

---

## Key Features by Module

### 🤖 Agent (`agent/core.py`)
- **LangGraph State Machine**: Robust agent with tool calling
- **Multi-Provider Support**: Ollama, OpenAI, Anthropic, Google, Grok
- **Analysis Levels**: Fast, Balanced, Deep
- **Memory Integration**: Context from ChromaDB
- **Tool Binding**: Automatic tool invocation and execution

### 💾 Memory (`memory/manager.py`)
- **ChromaDB**: Semantic search over conversations
- **SQLite**: Persistent message storage
- **User Facts**: Long-term memory with confidence scores
- **Conversation History**: Complete message tracking
- **Search**: Find relevant past interactions

### 🔍 Tools (`tools/`)
- **search.py**: 
  - Tavily API for deep analysis
  - DuckDuckGo fallback (no API key needed)
  - Quick and deep search modes
  
- **filesystem.py**:
  - Safe file listing, reading, writing
  - Path whitelist validation
  - Size and type restrictions
  
- **document_reader.py**:
  - PDF extraction (pypdf)
  - Word documents (python-docx)
  - Plain text files
  
- **image_analysis.py**:
  - Vision model support (OpenAI GPT-4V)
  - Base64 image encoding
  - Descriptive analysis

### 🎤 Voice (`voice/manager.py`)
- **STT (Speech-to-Text)**:
  - OpenAI Whisper
  - Google Cloud Speech-to-Text
  
- **TTS (Text-to-Speech)**:
  - Piper TTS (local/offline)
  - Google Cloud Text-to-Speech
  - Base64 audio responses

### 📡 API (`api/routes/`)
- **chat.py**: Message handling, WebSocket support
- **voice.py**: TTS/STT streaming
- **tools.py**: Tool access and management
- **memory.py**: Conversation and fact management
- **settings.py**: Configuration management
- **health.py**: Kubernetes probes

### ⚙️ Configuration (`config/settings.py`)
- Pydantic BaseSettings for environment validation
- Support for all major LLM providers
- Feature toggles for all tools
- Security and logging configuration

---

## File Statistics

```
Total Lines of Code: ~4,500
Total Files: 28
Python Modules: 20
Configuration Files: 8
Documentation Files: 3

Core Logic:
- agent/core.py: ~350 lines
- memory/manager.py: ~400 lines
- tools/*.py: ~500 lines combined
- voice/manager.py: ~350 lines
- api/routes/*.py: ~800 lines combined
```

---

## Dependencies Summary

### Core AI/ML
- `langchain` - LLM framework
- `langgraph` - Agent orchestration
- `ollama` - Local model support
- `openai` - GPT support
- `anthropic` - Claude support
- `langchain-google-genai` - Gemini support

### Vector/Memory
- `chromadb` - Vector database
- `sqlalchemy` - ORM

### Web Framework
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `websockets` - WebSocket support

### Voice
- `openai` (whisper) - Speech recognition
- `piper-tts` - Local TTS
- `SpeechRecognition` - Audio processing

### Tools
- `duckduckgo-search` - Web search
- `tavily-python` - Advanced search
- `pypdf` - PDF reading
- `python-docx` - Word documents
- `Pillow` - Image processing
- `opencv-python` - Computer vision

### Utilities
- `python-dotenv` - Environment management
- `pydantic` - Data validation
- `aiofiles` - Async file operations
- `httpx` - Async HTTP client
- `qrcode` - QR generation

**Total Dependencies**: ~45 packages

---

## API Endpoints Overview

### Chat Endpoints
```
POST   /api/chat/message              Send message
GET    /api/chat/history/{id}         Get conversation
DELETE /api/chat/history/{id}         Clear conversation
POST   /api/chat/message/with-file    Message with file
WS     /api/chat/ws/{user_id}/{conv}  WebSocket chat
```

### Voice Endpoints
```
POST   /api/voice/tts                 Text to speech
POST   /api/voice/tts/stream          Stream audio
POST   /api/voice/stt                 Speech to text
GET    /api/voice/voices              List voices
GET    /api/voice/languages           Supported languages
```

### Tools Endpoints
```
POST   /api/tools/search              Search internet
POST   /api/tools/filesystem/list     List files
GET    /api/tools/filesystem/read     Read file
POST   /api/tools/filesystem/write    Write file
GET    /api/tools/available           Available tools
```

### Memory Endpoints
```
GET    /api/memory/facts/{id}         Get user facts
POST   /api/memory/facts              Save fact
POST   /api/memory/search             Search memory
GET    /api/memory/history/{id}       Get history
DELETE /api/memory/history/{id}       Delete history
```

### Settings Endpoints
```
GET    /api/settings/                 Get settings
POST   /api/settings/analysis-level   Set analysis level
GET    /api/settings/llm-providers    Available providers
POST   /api/settings/llm-provider     Set provider
```

### Health Endpoints
```
GET    /api/health                    Basic health
GET    /api/health/detailed           Detailed status
GET    /api/ready                     Readiness probe
GET    /api/live                      Liveness probe
```

**Total Endpoints**: 30+

---

## Configuration Examples

### Using Ollama (Recommended for local)
```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral
```

### Using OpenAI
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

### Using Anthropic Claude
```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

### Analysis Levels
```env
ANALYSIS_LEVEL=fast        # Quick responses
ANALYSIS_LEVEL=balanced    # Default
ANALYSIS_LEVEL=deep        # Search & reasoning
```

---

## Quick Commands

### Local Development
```bash
python main.py                  # Start backend
uvicorn main:app --reload       # With auto-reload
```

### Docker
```bash
docker-compose up -d            # Start everything
docker-compose down -v          # Stop everything
docker-compose logs -f backend  # View logs
```

### Testing
```bash
curl http://localhost:8000/api/health
curl -X POST http://localhost:8000/api/chat/message \
  -H "X-API-Key: aiko-default-key" \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello","conversation_id":"test","user_id":"user1"}'
```

---

## Next Steps

1. **Setup**: Follow QUICKSTART.md (5 min)
2. **Explore**: Open `/docs` for API documentation
3. **Connect**: Use FRONTEND_INTEGRATION.md for frontend
4. **Configure**: Customize .env for your setup
5. **Deploy**: Use Docker for production

---

## Support & Documentation

- 📖 **Full Docs**: README.md
- ⚡ **Quick Start**: QUICKSTART.md
- 🔗 **Frontend Integration**: FRONTEND_INTEGRATION.md
- 📡 **API Docs**: http://localhost:8000/docs (interactive)
- 🐛 **Issues**: GitHub Issues
- 💬 **Discussion**: GitHub Discussions

---

## Performance Targets

**Response Times (P95)**:
- Fast mode: 500ms - 2s
- Balanced mode: 1s - 5s
- Deep mode: 5s - 15s

**Memory Usage**:
- Backend only: ~500MB
- With Ollama (mistral): ~4-5GB
- With all features: ~6-8GB

**Throughput**:
- Single instance: ~50-100 req/s
- Per-user concurrent: 5-10 sessions

---

## Security Checklist

- [ ] Change API_KEY in production
- [ ] Set DEBUG=false
- [ ] Use HTTPS/SSL
- [ ] Restrict CORS origins
- [ ] Enable request signing
- [ ] Implement rate limiting
- [ ] Validate all inputs
- [ ] Encrypt sensitive data
- [ ] Monitor and log access
- [ ] Regular security updates

---

## Deployment Checklist

- [ ] All dependencies installed
- [ ] Environment variables configured
- [ ] Data directories created
- [ ] Database initialized
- [ ] Health checks passing
- [ ] API documentation accessible
- [ ] Logs configured
- [ ] Monitoring setup
- [ ] Backups configured
- [ ] Load balancer configured (if needed)

---

**Version**: 1.0.0
**Last Updated**: 2024
**License**: MIT

Made with ❤️ for Aiko AI Assistant
