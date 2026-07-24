"""
Frontend Integration Examples
Example TypeScript code showing how to connect the Aiko frontend with the backend.
"""

# TypeScript / JavaScript Integration Examples

## 1. API Client Setup

```typescript
// src/lib/api.ts
import { ChatMessage, Conversation } from "@/lib/conversations";

const API_BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";
const API_KEY = process.env.REACT_APP_API_KEY || "aiko-default-key-change-in-production";

interface AikoAPIClient {
  chat: ChatAPI;
  voice: VoiceAPI;
  memory: MemoryAPI;
  settings: SettingsAPI;
}

class ChatAPI {
  async sendMessage(
    message: string,
    conversationId: string,
    userId: string,
    analysisLevel: string = "balanced"
  ): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/api/chat/message`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY,
      },
      body: JSON.stringify({
        message,
        conversation_id: conversationId,
        user_id: userId,
        analysis_level: analysisLevel,
      }),
    });

    if (!response.ok) throw new Error(`API Error: ${response.statusText}`);
    return response.json();
  }

  async getHistory(conversationId: string) {
    const response = await fetch(
      `${API_BASE_URL}/api/chat/history/${conversationId}`,
      {
        headers: { "X-API-Key": API_KEY },
      }
    );

    if (!response.ok) throw new Error("Failed to fetch history");
    return response.json();
  }

  connectWebSocket(
    userId: string,
    conversationId: string,
    onMessage: (msg: any) => void,
    onError: (err: any) => void
  ): WebSocket {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host.replace(":3000", ":8000")}/api/chat/ws/${userId}/${conversationId}`;

    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      onMessage(data);
    };

    ws.onerror = (error) => {
      onError(error);
    };

    return ws;
  }
}

class VoiceAPI {
  async synthesize(text: string, voice: string = "default"): Promise<string> {
    const response = await fetch(`${API_BASE_URL}/api/voice/tts`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY,
      },
      body: JSON.stringify({ text, voice }),
    });

    if (!response.ok) throw new Error("TTS failed");
    const data = await response.json();
    return data.audio_url;
  }

  async transcribe(audioFile: Blob): Promise<string> {
    const formData = new FormData();
    formData.append("file", audioFile);

    const response = await fetch(`${API_BASE_URL}/api/voice/stt`, {
      method: "POST",
      headers: { "X-API-Key": API_KEY },
      body: formData,
    });

    if (!response.ok) throw new Error("STT failed");
    const data = await response.json();
    return data.text;
  }
}

class MemoryAPI {
  async getUserFacts(userId: string) {
    const response = await fetch(`${API_BASE_URL}/api/memory/facts/${userId}`, {
      headers: { "X-API-Key": API_KEY },
    });

    if (!response.ok) throw new Error("Failed to fetch user facts");
    return response.json();
  }

  async saveUserFact(
    userId: string,
    fact: string,
    category: string = "general"
  ) {
    const response = await fetch(`${API_BASE_URL}/api/memory/facts`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY,
      },
      body: JSON.stringify({
        user_id: userId,
        fact,
        category,
        confidence: 0.8,
      }),
    });

    if (!response.ok) throw new Error("Failed to save fact");
    return response.json();
  }
}

class SettingsAPI {
  async getSettings() {
    const response = await fetch(`${API_BASE_URL}/api/settings/`, {
      headers: { "X-API-Key": API_KEY },
    });

    if (!response.ok) throw new Error("Failed to fetch settings");
    return response.json();
  }

  async setAnalysisLevel(level: string) {
    const response = await fetch(`${API_BASE_URL}/api/settings/analysis-level`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY,
      },
      body: JSON.stringify({ level }),
    });

    if (!response.ok) throw new Error("Failed to set analysis level");
    return response.json();
  }
}

export const aikoAPI: AikoAPIClient = {
  chat: new ChatAPI(),
  voice: new VoiceAPI(),
  memory: new MemoryAPI(),
  settings: new SettingsAPI(),
};
```

## 2. Chat Component Integration

```typescript
// src/components/ChatPanel.tsx
import { useState, useRef, useEffect } from "react";
import { aikoAPI } from "@/lib/api";

export function ChatPanel() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [analysisLevel, setAnalysisLevel] = useState("balanced");

  const conversationId = useRef("conv-" + Date.now()).current;
  const userId = "user-123"; // From auth context

  const handleSendMessage = async () => {
    if (!input.trim()) return;

    try {
      setIsLoading(true);

      const response = await aikoAPI.chat.sendMessage(
        input,
        conversationId,
        userId,
        analysisLevel
      );

      if (response.success) {
        // Add user message
        setMessages((prev) => [
          ...prev,
          {
            id: response.message_id,
            role: "user",
            text: input,
            at: Date.now(),
          },
        ]);

        // Add AI response
        setMessages((prev) => [
          ...prev,
          {
            id: Math.random().toString(),
            role: "aiko",
            text: response.response,
            at: Date.now(),
          },
        ]);

        setInput("");
      }
    } catch (error) {
      console.error("Chat error:", error);
      alert("Error sending message");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full gap-4">
      {/* Analysis Level Selector */}
      <div className="flex gap-2">
        {["fast", "balanced", "deep"].map((level) => (
          <button
            key={level}
            onClick={() => setAnalysisLevel(level)}
            className={`px-4 py-2 rounded ${
              analysisLevel === level
                ? "bg-blue-500 text-white"
                : "bg-gray-200"
            }`}
          >
            {level.charAt(0).toUpperCase() + level.slice(1)}
          </button>
        ))}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`p-4 rounded ${
              msg.role === "user"
                ? "bg-blue-100 text-blue-900"
                : "bg-gray-100 text-gray-900"
            }`}
          >
            {msg.text}
          </div>
        ))}
        {isLoading && <div className="text-gray-500">Aiko is thinking...</div>}
      </div>

      {/* Input */}
      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={(e) => e.key === "Enter" && handleSendMessage()}
          placeholder="Message Aiko..."
          className="flex-1 px-4 py-2 border rounded"
          disabled={isLoading}
        />
        <button
          onClick={handleSendMessage}
          disabled={isLoading}
          className="px-4 py-2 bg-blue-500 text-white rounded disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </div>
  );
}
```

## 3. WebSocket Real-time Chat

```typescript
// src/hooks/useAikoChat.ts
import { useEffect, useRef, useState } from "react";
import { aikoAPI } from "@/lib/api";

export function useAikoChat(userId: string, conversationId: string) {
  const [messages, setMessages] = useState<any[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    // Connect WebSocket
    wsRef.current = aikoAPI.chat.connectWebSocket(
      userId,
      conversationId,
      (message) => {
        if (message.success) {
          setMessages((prev) => [
            ...prev,
            {
              id: Math.random().toString(),
              role: "aiko",
              text: message.response,
              at: Date.now(),
            },
          ]);
        }
      },
      (error) => {
        console.error("WebSocket error:", error);
        setIsConnected(false);
      }
    );

    wsRef.current.onopen = () => setIsConnected(true);
    wsRef.current.onclose = () => setIsConnected(false);

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [userId, conversationId]);

  const sendMessage = (message: string) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      // Add user message
      setMessages((prev) => [
        ...prev,
        {
          id: Math.random().toString(),
          role: "user",
          text: message,
          at: Date.now(),
        },
      ]);

      // Send to backend
      wsRef.current.send(JSON.stringify({ message }));
    }
  };

  return { messages, isConnected, sendMessage };
}
```

## 4. Voice Integration

```typescript
// src/hooks/useAikoVoice.ts
import { aikoAPI } from "@/lib/api";

export function useAikoVoice() {
  const handleSpeak = async (text: string) => {
    try {
      const audioUrl = await aikoAPI.voice.synthesize(text);
      const audio = new Audio(audioUrl);
      await audio.play();
    } catch (error) {
      console.error("TTS error:", error);
    }
  };

  const handleListenForSpeech = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      const chunks: BlobPart[] = [];

      recorder.ondataavailable = (e) => chunks.push(e.data);
      recorder.onstop = async () => {
        const blob = new Blob(chunks, { type: "audio/wav" });
        const text = await aikoAPI.voice.transcribe(blob);
        console.log("Recognized text:", text);
        return text;
      };

      recorder.start();
      setTimeout(() => recorder.stop(), 5000); // Record for 5 seconds
    } catch (error) {
      console.error("STT error:", error);
    }
  };

  return { handleSpeak, handleListenForSpeech };
}
```

## 5. Settings Management

```typescript
// src/context/AikoSettingsContext.tsx
import { createContext, useContext, useEffect, useState } from "react";
import { aikoAPI } from "@/lib/api";

interface AikoSettings {
  analysisLevel: "fast" | "balanced" | "deep";
  voice: string;
  language: string;
}

const defaultSettings: AikoSettings = {
  analysisLevel: "balanced",
  voice: "default",
  language: "en",
};

const SettingsContext = createContext<{
  settings: AikoSettings;
  updateSettings: (settings: Partial<AikoSettings>) => Promise<void>;
}>({
  settings: defaultSettings,
  updateSettings: async () => {},
});

export function AikoSettingsProvider({ children }: { children: React.ReactNode }) {
  const [settings, setSettings] = useState(defaultSettings);

  const updateSettings = async (updates: Partial<AikoSettings>) => {
    if (updates.analysisLevel) {
      await aikoAPI.settings.setAnalysisLevel(updates.analysisLevel);
    }
    setSettings((prev) => ({ ...prev, ...updates }));
  };

  useEffect(() => {
    // Load settings on mount
    aikoAPI.settings.getSettings().then((data) => {
      setSettings((prev) => ({
        ...prev,
        analysisLevel: data.analysis_level,
      }));
    });
  }, []);

  return (
    <SettingsContext.Provider value={{ settings, updateSettings }}>
      {children}
    </SettingsContext.Provider>
  );
}

export function useAikoSettings() {
  return useContext(SettingsContext);
}
```

## 6. Environment Setup

```typescript
// .env.local
REACT_APP_API_URL=http://localhost:8000
REACT_APP_API_KEY=aiko-default-key-change-in-production

# For production
# REACT_APP_API_URL=https://api.yourdomain.com
# REACT_APP_API_KEY=your-prod-api-key
```
