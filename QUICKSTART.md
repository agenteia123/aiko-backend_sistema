# 🚀 Aiko Backend - Quick Start Guide

Get Aiko running in **5 minutes**!

## Option 1: Docker (Recommended - Easiest)

### Prerequisites
- Docker and Docker Compose installed

### Start Everything
```bash
# Clone the repository
git clone https://github.com/yourusername/aiko-backend.git
cd aiko-backend

# Copy environment file
cp .env.template .env

# Start with Docker Compose
docker-compose up -d

# Check if running
curl http://localhost:8000/api/health
```

**Done!** Backend running at `http://localhost:8000`

---

## Option 2: Local Installation

### Prerequisites
- Python 3.11+
- pip
- Ollama (optional, for local inference)

### Step-by-Step

#### 1. Setup (2 min)
```bash
# Clone
git clone https://github.com/yourusername/aiko-backend.git
cd aiko-backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt
```

#### 2. Configure (1 min)
```bash
# Copy environment template
cp .env.template .env

# Edit .env (open in your editor)
# For now, defaults are fine - Ollama will be used locally
```

#### 3. Setup Ollama (Optional, for local models)
```bash
# Install Ollama from https://ollama.ai
# Then pull a model:
ollama pull mistral
```

#### 4. Run Backend (2 min)
```bash
# Create necessary directories
mkdir -p data/{chroma,uploads,documents}

# Start backend
python main.py
```

**Output should show:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
✅ Services initialized
```

#### 5. Verify
```bash
# In another terminal
curl http://localhost:8000/api/health

# Should return:
# {"status":"healthy","version":"1.0.0","app":"Aiko AI Assistant"}
```

---

## Quick Tests

### Health Check
```bash
curl http://localhost:8000/api/health
```

### API Documentation
Open in browser: `http://localhost:8000/docs`

### Send a Message
```bash
curl -X POST http://localhost:8000/api/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello Aiko!",
    "conversation_id": "test-conv-1",
    "user_id": "test-user-1",
    "analysis_level": "balanced"
  }'
```

### Text-to-Speech
```bash
curl -X POST http://localhost:8000/api/voice/tts \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello, this is Aiko!"
  }'
```

---

## Connecting Frontend

### Frontend Configuration
In your Aiko frontend (TypeScript/React):

```typescript
// src/config/api.ts
const API_BASE_URL = "http://localhost:8000";
const API_KEY = "aiko-default-key-change-in-production";

export const apiClient = {
  async sendMessage(message: string, conversationId: string) {
    const response = await fetch(
      `${API_BASE_URL}/api/chat/message`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": API_KEY,
        },
        body: JSON.stringify({
          message,
          conversation_id: conversationId,
          user_id: "user-123", // Get from auth
          analysis_level: "balanced",
        }),
      }
    );
    
    return response.json();
  },
};
```

---

## Environment Variables Explained

```env
# Use local Ollama (default)
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral

# Or use OpenAI
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-... # Get from https://platform.openai.com

# API Security
API_KEY=your-secret-api-key

# Analysis Level
ANALYSIS_LEVEL=balanced  # fast, balanced, or deep
```

---

## Troubleshooting

### Port 8000 Already in Use
```bash
# Find and kill process using port 8000
# macOS/Linux:
lsof -i :8000 | grep LISTEN | awk '{print $2}' | xargs kill -9

# Windows:
netstat -ano | findstr :8000
# Then: taskkill /PID <PID> /F
```

### Ollama Not Connecting
```bash
# Start Ollama
ollama serve

# Verify it's running
curl http://localhost:11434/api/tags

# Pull a model if needed
ollama pull mistral
```

### Out of Memory
```env
# Use smaller model
OLLAMA_MODEL=neural-chat  # Smaller than mistral
# Or disable features
ENABLE_IMAGE_ANALYSIS=false
```

### Database Errors
```bash
# Reset database
rm -rf data/chroma data/aiko.db

# Restart backend
python main.py
```

---

## Development Tips

### Auto-Reload on Changes
```bash
# Install dev dependencies
pip install uvicorn[standard]

# Run with reload
uvicorn main:app --reload
```

### Debug Mode
```env
DEBUG=true
LOG_LEVEL=DEBUG
```

### Access API Docs
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## Next Steps

1. ✅ Backend running
2. 📱 Connect your frontend
3. 🔑 Change API key in production
4. 🚀 Deploy to production
5. 📚 Read full README.md for detailed docs

---

## Common Commands

### Stop Backend
```bash
# Press Ctrl+C in terminal
```

### View Logs
```bash
# Follow logs in Docker
docker-compose logs -f backend

# Local Python
# Output appears in terminal
```

### Reset Everything
```bash
# Docker
docker-compose down -v

# Local
rm -rf data/ venv/
```

---

## What's Working?

✅ Chat with AI
✅ Memory (conversation history)
✅ Internet search
✅ File operations
✅ Voice (TTS/STT basics)
✅ WebSocket support
✅ Real-time responses
✅ Multiple LLM providers
✅ API documentation

---

## Performance

**Typical Response Times:**
- Fast mode: 500ms - 2s
- Balanced mode: 1s - 5s
- Deep mode: 5s - 15s

**Memory Usage:**
- Backend alone: ~500MB
- With Ollama (mistral): ~4GB
- With context: ~6GB total

---

## Production Deployment

### Before Going Live
1. Change `API_KEY` in `.env`
2. Set `DEBUG=false`
3. Use environment-specific configs
4. Setup HTTPS/SSL
5. Configure CORS properly
6. Enable rate limiting
7. Setup monitoring

### Quick Deployment with Docker
```bash
docker-compose -f docker-compose.yml up -d
```

---

## Getting Help

- 📖 Full docs: `README.md`
- 🔗 API docs: `http://localhost:8000/docs`
- 🐛 Issues: Check GitHub issues
- 💬 Discussion: GitHub discussions

---

## Success Indicators

You're ready when:
- ✅ `curl http://localhost:8000/api/health` returns `{"status":"healthy"}`
- ✅ Frontend connects without CORS errors
- ✅ Chat responds in `http://localhost:8000/docs`
- ✅ Memory saves conversation history

---

**Happy coding! 🚀**

Need help? Check the full README.md or open an issue on GitHub.
