# 🤖 Aiko AI Assistant Backend

A professional, production-ready Python backend for the Aiko AI companion. Powered by LangGraph, LangChain, and multiple AI providers with built-in memory, voice, tools, and real-time communication.

## ✨ Features

### Core AI Engine
- **LangGraph + LangChain**: Robust agent architecture for complex reasoning
- **Multi-Provider Support**:
  - 🔴 **Ollama** (Local/Offline)
  - 🟣 **OpenAI** (GPT-4, GPT-3.5)
  - 🟤 **Anthropic** (Claude)
  - 🔵 **Google** (Gemini)
  - ⚫ **Grok** (X.AI)
- **Analysis Levels**: Fast ⚡, Balanced ⚖️, Deep 🔍

### Memory System
- **ChromaDB**: Vector database for semantic search
- **SQLite**: Persistent conversation storage
- **Long-term Memory**: User facts and context
- **Conversation History**: Complete message tracking

### Voice Integration
- **Speech-to-Text (STT)**:
  - OpenAI Whisper
  - Google Cloud Speech-to-Text
- **Text-to-Speech (TTS)**:
  - Piper (Local/Offline)
  - Google Cloud Text-to-Speech

### Smart Tools
- 🔍 **Internet Search**: Tavily API + DuckDuckGo fallback
- 📁 **Filesystem Access**: Safe file operations
- 📄 **Document Reader**: PDF, Word, TXT support
- 🖼️ **Image Analysis**: Vision model support

### API Features
- FastAPI with WebSocket support
- Real-time streaming responses
- File upload handling
- REST + WebSocket endpoints
- Comprehensive error handling

### Security & Quality
- API Key authentication
- Rate limiting ready
- Structured logging
- Production-ready configuration
- Kubernetes-ready health checks

## 📋 Requirements

- **Python**: 3.11+
- **RAM**: 4GB+ (8GB+ for deep analysis)
- **Disk**: 10GB+ (for models and data)
- **Optional**: Ollama, GPU for local inference

## 🚀 Installation

### 1. Clone Repository
```bash
git clone https://github.com/yourusername/aiko-backend.git
cd aiko-backend
```

### 2. Create Virtual Environment
```bash
python -m venv venv

# Linux/macOS
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Setup Environment
```bash
cp .env.template .env
# Edit .env with your configuration
nano .env
```

### 5. Create Data Directories
```bash
mkdir -p data/{chroma,uploads,documents,logs}
```

## ⚙️ Configuration

### Environment Variables (`.env`)

#### LLM Provider Selection
```env
# Use Ollama (default, local/offline)
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral

# Or use OpenAI
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...

# Or Anthropic Claude
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Or Google Gemini
LLM_PROVIDER=google
GOOGLE_API_KEY=...

# Or Grok
LLM_PROVIDER=grok
GROK_API_KEY=...
```

#### Analysis Level
```env
# fast - Quick responses, minimal search
# balanced - Good balance (default)
# deep - Comprehensive analysis with search
ANALYSIS_LEVEL=balanced
```

#### Memory Configuration
```env
CHROMA_PERSIST_DIR=./data/chroma
DB_PATH=./data/aiko.db
MEMORY_SEARCH_LIMIT=5
```

#### Voice Configuration
```env
# Speech-to-Text
STT_PROVIDER=whisper  # or google
OPENAI_API_KEY=sk-...  # Required for Whisper

# Text-to-Speech
TTS_PROVIDER=piper  # or google
PIPER_MODEL=en_US-amy-medium
```

#### Security
```env
API_KEY=aiko-change-this-in-production
JWT_SECRET=your-jwt-secret
DEBUG=false
```

## 🏃 Running the Backend

### Local Development
```bash
# Basic start
python main.py

# With auto-reload
uvicorn main:app --reload

# With specific host/port
uvicorn main:app --host 0.0.0.0 --port 8000

# With logging
uvicorn main:app --log-level info
```

### Production
```bash
# Using Gunicorn
gunicorn main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker

# Using Docker
docker build -t aiko-backend .
docker run -p 8000:8000 aiko-backend
```

## 📡 API Endpoints

### Chat
```
POST   /api/chat/message              - Send message
GET    /api/chat/history/{conv_id}    - Get conversation history
DELETE /api/chat/history/{conv_id}    - Clear conversation
WS     /api/chat/ws/{user_id}/{conv}  - WebSocket chat
```

### Voice
```
POST   /api/voice/tts                 - Text to Speech
POST   /api/voice/tts/stream          - Stream TTS audio
POST   /api/voice/stt                 - Speech to Text
GET    /api/voice/voices              - List voices
GET    /api/voice/languages           - Supported languages
```

### Tools
```
POST   /api/tools/search              - Internet search
POST   /api/tools/filesystem/list     - List files
GET    /api/tools/filesystem/read     - Read file
POST   /api/tools/filesystem/write    - Write file
GET    /api/tools/available           - Available tools
```

### Memory
```
GET    /api/memory/facts/{user_id}    - Get user facts
POST   /api/memory/facts              - Save user fact
POST   /api/memory/search             - Search memory
GET    /api/memory/history/{conv_id}  - Get history
DELETE /api/memory/history/{conv_id}  - Delete history
```

### Settings
```
GET    /api/settings/                 - Get settings
POST   /api/settings/analysis-level   - Set analysis level
GET    /api/settings/llm-providers    - Available providers
POST   /api/settings/llm-provider     - Set LLM provider
GET    /api/settings/health           - Health check
```

### Health
```
GET    /api/health                    - Basic health check
GET    /api/health/detailed           - Detailed status
GET    /api/ready                     - Readiness probe
GET    /api/live                      - Liveness probe
```

## 🔌 Frontend Connection

The backend is designed to work seamlessly with the Aiko frontend.

### Basic Usage Example
```typescript
// Initialize connection
const API_KEY = "your-api-key";
const BASE_URL = "http://localhost:8000";

// Send message
const response = await fetch(`${BASE_URL}/api/chat/message`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY,
  },
  body: JSON.stringify({
    message: "Hello, Aiko!",
    conversation_id: "conv-123",
    user_id: "user-123",
    analysis_level: "balanced",
  }),
});

const data = await response.json();
console.log(data.response);

// WebSocket (real-time)
const ws = new WebSocket(
  `ws://localhost:8000/api/chat/ws/user-123/conv-123`
);

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log("Response:", data.response);
};

ws.send(JSON.stringify({
  message: "What's the weather?",
  analysis_level: "balanced",
}));
```

## 🛠️ Local Model Setup (Ollama)

### Install Ollama
```bash
# macOS
brew install ollama

# Linux
curl https://ollama.ai/install.sh | sh

# Windows
# Download from https://ollama.ai
```

### Start Ollama
```bash
ollama serve
```

### Pull a Model
```bash
# Mistral (7B, recommended)
ollama pull mistral

# Or other models
ollama pull llama2
ollama pull neural-chat
ollama pull openhermes
```

### Verify
```bash
curl http://localhost:11434/api/tags
```

## 📦 Project Structure

```
aiko-backend/
├── main.py                 # Entry point
├── requirements.txt        # Dependencies
├── .env.template          # Environment template
│
├── agent/
│   ├── core.py           # LangGraph agent
│   └── __init__.py
│
├── core/
│   ├── llm_factory.py     # LLM provider factory
│   ├── services.py        # Service manager
│   └── __init__.py
│
├── config/
│   ├── settings.py        # Configuration
│   └── __init__.py
│
├── memory/
│   ├── manager.py         # ChromaDB + SQLite
│   └── __init__.py
│
├── tools/
│   ├── search.py          # Internet search
│   ├── filesystem.py      # File operations
│   ├── document_reader.py # PDF, Word, TXT
│   ├── image_analysis.py  # Vision models
│   └── __init__.py
│
├── voice/
│   ├── manager.py         # STT & TTS
│   └── __init__.py
│
├── api/
│   ├── auth.py           # Authentication
│   ├── routes/
│   │   ├── chat.py       # Chat endpoints
│   │   ├── voice.py      # Voice endpoints
│   │   ├── tools.py      # Tools endpoints
│   │   ├── memory.py     # Memory endpoints
│   │   ├── settings.py   # Settings endpoints
│   │   ├── health.py     # Health endpoints
│   │   └── __init__.py
│   └── __init__.py
│
├── data/
│   ├── chroma/           # Vector database
│   ├── aiko.db           # SQLite database
│   └── uploads/          # User uploads
│
└── logs/
    └── app.log           # Application logs
```

## 🧪 Testing

### Quick Test
```bash
# Test health endpoint
curl http://localhost:8000/api/health

# Test with API key
curl -H "X-API-Key: your-api-key" \
  http://localhost:8000/api/settings
```

### Full Test
```bash
# Using Python
python -m pytest tests/

# Manual endpoint test
curl -X POST http://localhost:8000/api/chat/message \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello!",
    "conversation_id": "test-conv",
    "user_id": "test-user"
  }'
```

## 🔐 Security Considerations

1. **Change default API key** in production
2. **Use HTTPS** in production
3. **Implement rate limiting** for production
4. **Restrict CORS origins** by domain
5. **Validate file uploads** for size and type
6. **Use strong JWT secrets**
7. **Enable request logging** for debugging

## 🚨 Troubleshooting

### Ollama Connection Failed
```bash
# Make sure Ollama is running
ollama serve

# Check connection
curl http://localhost:11434/api/tags
```

### Memory Database Error
```bash
# Reset database
rm -rf data/chroma data/aiko.db
python main.py
```

### Voice Features Not Working
```bash
# Install missing dependencies
pip install openai piper-tts SpeechRecognition

# For Piper TTS
pip install piper-tts
```

### WebSocket Connection Issues
```
# Check firewall allows port 8000
# Verify backend is running
# Check browser console for CORS errors
```

## 📚 API Documentation

Full interactive documentation available at:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## 🤝 Integration with Frontend

The backend is designed to work with the Aiko TypeScript frontend:

```typescript
// Frontend integration example
import { AikoAPI } from './api';

const api = new AikoAPI({
  baseURL: 'http://localhost:8000',
  apiKey: 'your-api-key',
});

// Send message
const response = await api.chat.sendMessage({
  message: 'Hello Aiko!',
  conversationId: 'conv-123',
});

// Real-time chat with WebSocket
api.chat.connectWebSocket((message) => {
  console.log('AI:', message.response);
});
```

## 🐳 Docker Support

### Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose
```yaml
version: '3.8'
services:
  backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      - LLM_PROVIDER=ollama
      - OLLAMA_BASE_URL=http://ollama:11434
    depends_on:
      - ollama
  
  ollama:
    image: ollama/ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama-data:/root/.ollama
```

## 📈 Performance Tips

1. **Use Ollama locally** for better latency
2. **Adjust OLLAMA_TIMEOUT** based on model size
3. **Limit MEMORY_SEARCH_LIMIT** for speed
4. **Use "fast" analysis level** for quick responses
5. **Enable HTTP/2** for better performance
6. **Monitor logs** for bottlenecks

## 🎯 Next Steps

1. ✅ Install dependencies
2. ✅ Configure `.env` file
3. ✅ Start Ollama (if using local)
4. ✅ Run backend: `python main.py`
5. ✅ Connect frontend to `http://localhost:8000`
6. ✅ Access API docs at `http://localhost:8000/docs`

## 📝 Environment Checklist

- [ ] Python 3.11+ installed
- [ ] Virtual environment created
- [ ] Dependencies installed
- [ ] `.env` file configured
- [ ] API key set
- [ ] Data directories created
- [ ] Ollama installed (if using local)
- [ ] Backend starts without errors
- [ ] Health check passes

## 🐛 Bug Reports & Features

Found an issue? Have a feature request?
- Open an issue on GitHub
- Include error logs and reproduction steps
- Specify your Python version and OS

## 📄 License

MIT License - Feel free to use in personal and commercial projects

## 🙏 Support

For help:
- Check the documentation at `/docs`
- Review troubleshooting section
- Check GitHub issues
- Contact the team

---

**Made with ❤️ for Aiko AI Assistant**

Happy Coding! 🚀
