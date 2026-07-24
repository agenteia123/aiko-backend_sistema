"""Shared data models for Aiko backend."""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


# Chat Models
class ChatMessage(BaseModel):
    """Chat message model matching frontend specification."""
    id: str = Field(..., description="Unique message ID")
    role: str = Field(..., description="'user' or 'aiko'")
    text: str = Field(..., description="Message content")
    at: int = Field(..., description="Timestamp in milliseconds")
    attachments: Optional[List[dict]] = Field(None, description="File/image attachments")
    tool: Optional[dict] = Field(None, description="Tool activity trace")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "msg-123",
                "role": "user",
                "text": "Hello, Aiko!",
                "at": 1699564800000,
                "attachments": None,
            }
        }


class Conversation(BaseModel):
    """Conversation model."""
    id: str = Field(..., description="Unique conversation ID")
    title: str = Field(..., description="Conversation title")
    createdAt: int = Field(..., description="Creation timestamp")
    updatedAt: int = Field(..., description="Last update timestamp")
    messages: List[ChatMessage] = Field(default_factory=list)

    class Config:
        json_schema_extra = {
            "example": {
                "id": "conv-123",
                "title": "Nueva conversación",
                "createdAt": 1699564800000,
                "updatedAt": 1699564800000,
                "messages": [],
            }
        }


class UserProfile(BaseModel):
    """User profile model."""
    user_id: str = Field(..., description="Unique user ID")
    username: Optional[str] = Field(None, description="User's display name")
    language: str = Field(default="es", description="Preferred language")
    timezone: Optional[str] = Field(None, description="User's timezone")
    preferences: dict = Field(default_factory=dict, description="User preferences")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class UserFact(BaseModel):
    """User fact model for long-term memory."""
    id: str
    user_id: str
    fact: str
    category: str
    confidence: float
    created_at: datetime


class ToolCall(BaseModel):
    """Tool invocation model."""
    name: str = Field(..., description="Tool name")
    args: dict = Field(default_factory=dict, description="Tool arguments")
    result: Optional[str] = Field(None, description="Tool result")
    status: str = Field(default="pending", description="pending, running, done, error")
    error: Optional[str] = Field(None, description="Error message if any")


class AgentResponse(BaseModel):
    """AI agent response model."""
    success: bool
    response: str
    message_id: str
    timestamp: int
    tool_calls: Optional[List[ToolCall]] = None
    analysis_metadata: Optional[dict] = None
    error: Optional[str] = None


# Search Models
class SearchResult(BaseModel):
    """Search result model."""
    title: str
    url: str
    snippet: str
    source: str


class SearchResponse(BaseModel):
    """Search response model."""
    success: bool
    query: str
    results: List[SearchResult]
    total_results: int


# Voice Models
class AudioSegment(BaseModel):
    """Audio segment model."""
    audio_data: str = Field(..., description="Base64 encoded audio")
    duration: float = Field(..., description="Duration in seconds")
    sample_rate: int = Field(default=16000)
    channels: int = Field(default=1)


class TranscriptionResult(BaseModel):
    """Speech-to-text result."""
    success: bool
    text: str
    language: str
    confidence: float
    duration: Optional[float] = None


class VoiceOptions(BaseModel):
    """Voice configuration options."""
    provider: str
    voice: str
    language: str
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    pitch: float = Field(default=1.0, ge=0.5, le=2.0)


# File Models
class FileInfo(BaseModel):
    """File information model."""
    name: str
    path: str
    size: int
    type: str
    created_at: datetime
    modified_at: datetime


class DocumentContent(BaseModel):
    """Document content model."""
    filename: str
    content: str
    type: str
    pages: Optional[int] = None
    language: Optional[str] = None


# Settings Models
class AnalysisLevelConfig(BaseModel):
    """Analysis level configuration."""
    level: str = Field(..., description="fast, balanced, or deep")
    max_search_results: int
    timeout_seconds: int
    use_deep_reasoning: bool


class LLMConfig(BaseModel):
    """LLM configuration."""
    provider: str
    model: str
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096)
    top_p: float = Field(default=0.9)


class SystemConfig(BaseModel):
    """System configuration."""
    app_name: str
    version: str
    debug: bool
    max_file_size_mb: int = Field(default=50)
    allowed_file_types: List[str] = Field(
        default_factory=lambda: ["pdf", "txt", "docx", "jpg", "png"]
    )
    max_conversation_length: int = Field(default=100)


# Affection/Gamification Models
class AffectionState(BaseModel):
    """Aiko affection state."""
    user_id: str
    level: float = Field(default=50.0, ge=0.0, le=100.0)
    daily_interactions: int = Field(default=0)
    favorite_topics: List[str] = Field(default_factory=list)
    mood: Optional[str] = Field(default="neutral")
    last_interaction: Optional[datetime] = None


class Achievement(BaseModel):
    """User achievement."""
    id: str
    title: str
    description: str
    icon: Optional[str] = None
    unlocked: bool = False
    unlocked_at: Optional[datetime] = None


class Statistics(BaseModel):
    """User statistics."""
    user_id: str
    total_messages: int
    total_conversations: int
    average_response_time_ms: float
    favorite_tools: List[str]
    languages_used: List[str]
    created_at: datetime
    updated_at: datetime


# Error Models
class ErrorResponse(BaseModel):
    """Error response model."""
    success: bool = False
    error: str
    error_code: Optional[str] = None
    details: Optional[dict] = None
    timestamp: datetime = Field(default_factory=datetime.now)


# Health Models
class HealthStatus(BaseModel):
    """Service health status."""
    status: str
    timestamp: datetime
    version: str
    services: dict


class ReadinessStatus(BaseModel):
    """Readiness probe status."""
    ready: bool
    checks: dict


# WebSocket Models
class WebSocketMessage(BaseModel):
    """WebSocket message model."""
    type: str  # "message", "typing", "tool", "error"
    data: dict
    timestamp: Optional[int] = None


class TypingIndicator(BaseModel):
    """Typing indicator message."""
    user_id: str
    is_typing: bool
    timestamp: int


# Batch Operation Models
class BatchMessage(BaseModel):
    """Batch message for processing multiple requests."""
    messages: List[str]
    conversation_id: str
    user_id: str


class BatchResponse(BaseModel):
    """Batch processing response."""
    success: bool
    results: List[AgentResponse]
    total_time_ms: float
