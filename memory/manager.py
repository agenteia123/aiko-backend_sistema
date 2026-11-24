"""Memory management system using ChromaDB and SQLite."""

import logging
import asyncio
import queue
import sqlite3
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from config.settings import settings


logger = logging.getLogger(__name__)


class MemoryManager:
    """Manage conversation memory and long-term knowledge."""
    
    _instance = None
    _chroma_client = None
    _db_connection = None
    
    def __init__(self):
        """Initialize memory manager."""
        self.chroma_persist_dir = Path(settings.CHROMA_PERSIST_DIR)
        self.db_path = Path(settings.DB_PATH)
        self.chroma = None
        self.conversations_collection = None
        self.knowledge_collection = None
        self.user_facts_collection = None
        self._chroma_write_queue = queue.Queue(maxsize=2000)
        self._chroma_worker = None
        self._chroma_worker_lock = threading.Lock()
        
        # Initialize ChromaDB
        self._init_chroma()
        
        # Initialize SQLite
        self._init_sqlite()
    
    @classmethod
    async def initialize(cls):
        """Initialize the memory manager singleton."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    async def shutdown(cls):
        """Shutdown memory manager."""
        instance = cls._instance
        if instance:
            instance._stop_chroma_worker()
            if instance._db_connection:
                instance._db_connection.close()
                instance._db_connection = None
            cls._instance = None
            logger.info("✅ Memory manager shut down")
    
    @classmethod
    async def get_instance(cls) -> "MemoryManager":
        """Get the memory manager instance."""
        if cls._instance is None:
            await cls.initialize()
        return cls._instance
    
    def _init_chroma(self):
        """Initialize ChromaDB client (nueva configuración)."""
        try:
            from chromadb import PersistentClient
            
            # Disable optional telemetry: it was generating PostHog errors on startup.
            self.chroma = PersistentClient(
                path=str(self.chroma_persist_dir),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            
            # Create or get collections
            self.conversations_collection = self.chroma.get_or_create_collection(
                name="conversations",
                metadata={"hnsw:space": "cosine"}
            )
            self.knowledge_collection = self.chroma.get_or_create_collection(
                name="knowledge",
                metadata={"hnsw:space": "cosine"}
            )
            self.user_facts_collection = self.chroma.get_or_create_collection(
                name="user_facts",
                metadata={"hnsw:space": "cosine"}
            )
            
            self._start_chroma_worker()
            logger.info("✅ ChromaDB initialized (nueva configuración)")
        except Exception as e:
            logger.exception("Failed to initialize ChromaDB: %s", e)
            self.chroma = None
            self.conversations_collection = None
            self.knowledge_collection = None
            self.user_facts_collection = None

    def _start_chroma_worker(self) -> None:
        """Run slow Chroma writes away from the FastAPI event loop."""
        if self.chroma is None:
            return
        with self._chroma_worker_lock:
            if self._chroma_worker and self._chroma_worker.is_alive():
                return
            self._chroma_worker = threading.Thread(
                target=self._chroma_write_loop,
                name="aiko-chroma-writer",
                daemon=True,
            )
            self._chroma_worker.start()

    def _chroma_write_loop(self) -> None:
        while True:
            item = self._chroma_write_queue.get()
            try:
                if item is None:
                    return
                collection, ids, documents, metadatas = item
                collection.add(ids=ids, documents=documents, metadatas=metadatas)
            except Exception:
                logger.exception("No se pudo indexar un registro en ChromaDB")
            finally:
                self._chroma_write_queue.task_done()

    def _queue_chroma_add(
        self,
        collection,
        record_id: str,
        document: str,
        metadata: dict,
    ) -> bool:
        if collection is None or not self._chroma_worker or not self._chroma_worker.is_alive():
            return False
        try:
            self._chroma_write_queue.put_nowait(
                (collection, [record_id], [document], [metadata])
            )
            return True
        except queue.Full:
            logger.warning(
                "Cola de ChromaDB llena; el registro queda guardado en SQLite "
                "pero no se indexará semánticamente ahora"
            )
            return False

    def _stop_chroma_worker(self) -> None:
        worker = self._chroma_worker
        if not worker or not worker.is_alive():
            return
        try:
            self._chroma_write_queue.put(None, timeout=1)
        except queue.Full:
            logger.warning("Cola de ChromaDB llena durante el cierre; el escritor seguirá como daemon")
        worker.join(timeout=2)
        if worker.is_alive():
            logger.warning("El escritor ChromaDB sigue procesando; se cerrará al salir del proceso")


    def _init_sqlite(self):
        """Initialize SQLite database."""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._db_connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False
            )
            
            cursor = self._db_connection.cursor()
            
            # Create tables
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_facts (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    fact TEXT NOT NULL,
                    category TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    confidence REAL DEFAULT 0.8
                )
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_id ON messages(user_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversation_id ON messages(conversation_id)
            """)
            
            self._db_connection.commit()
            logger.info("✅ SQLite database initialized")
        except Exception as e:
            logger.error(f"Failed to initialize SQLite: {e}")
            self._db_connection = None
    
    async def save_message(
        self,
        user_id: str,
        conversation_id: str,
        role: str,
        content: str,
        metadata: dict = None,
    ) -> str:
        """Save a message to memory."""
        import uuid
        
        message_id = str(uuid.uuid4())
        
        try:
            # Save to SQLite
            if self._db_connection:
                cursor = self._db_connection.cursor()
                cursor.execute("""
                    INSERT INTO messages
                    (id, user_id, conversation_id, role, content, metadata)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    message_id,
                    user_id,
                    conversation_id,
                    role,
                    content,
                    json.dumps(metadata or {})
                ))
                self._db_connection.commit()
            
            # Save to ChromaDB for semantic search
            if self.chroma and self.conversations_collection is not None:
                queued = self._queue_chroma_add(
                    self.conversations_collection,
                    message_id,
                    content,
                    {
                        "user_id": user_id,
                        "conversation_id": conversation_id,
                        "role": role,
                        "timestamp": datetime.now().isoformat(),
                    },
                )
                if not queued:
                    logger.warning("Mensaje guardado en SQLite; ChromaDB no pudo aceptar el índice")
            
            return message_id
        except Exception as e:
            logger.error(f"Error saving message: {e}")
            return message_id
    
    async def search_relevant(
        self,
        query: str,
        user_id: str,
        limit: int = 5,
    ) -> list[dict]:
        """Search for relevant past messages."""
        try:
            if not self.chroma or not self.conversations_collection:
                return []
            
            results = await asyncio.to_thread(
                self.conversations_collection.query,
                query_texts=[query],
                n_results=limit,
                where={"user_id": user_id},
            )
            
            return [
                {
                    "id": id_,
                    "content": doc,
                    "metadata": meta,
                }
                for id_, doc, meta in zip(
                    results["ids"][0],
                    results["documents"][0],
                    results["metadatas"][0],
                )
            ]
        except Exception as e:
            logger.error(f"Error searching memory: {e}")
            return []
    
    async def get_latest_assistant_reply(self, conversation_id: str, user_id: str) -> str:
        """Read the last assistant reply for this user and conversation."""
        if not self._db_connection:
            return ""
        row = self._db_connection.execute(
            """
            SELECT content FROM messages
            WHERE conversation_id = ? AND user_id = ? AND role = 'assistant'
            ORDER BY timestamp DESC, rowid DESC LIMIT 1
            """,
            (conversation_id, user_id),
        ).fetchone()
        return row[0] if row else ""

    async def get_conversation_history(
        self,
        conversation_id: str,
    ) -> list[dict]:
        """Get full conversation history."""
        try:
            if not self._db_connection:
                return []
            
            cursor = self._db_connection.cursor()
            cursor.execute("""
                SELECT id, role, content, timestamp
                FROM messages
                WHERE conversation_id = ?
                ORDER BY timestamp ASC
            """, (conversation_id,))
            
            rows = cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "role": row[1],
                    "content": row[2],
                    "timestamp": row[3],
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Error getting conversation history: {e}")
            return []
    
    async def save_user_fact(
        self,
        user_id: str,
        fact: str,
        category: str = "general",
        confidence: float = 0.8,
    ) -> str:
        """Save a fact about the user."""
        import uuid
        
        fact_id = str(uuid.uuid4())
        
        try:
            if self._db_connection:
                cursor = self._db_connection.cursor()
                cursor.execute("""
                    INSERT INTO user_facts
                    (id, user_id, fact, category, confidence)
                    VALUES (?, ?, ?, ?, ?)
                """, (fact_id, user_id, fact, category, confidence))
                self._db_connection.commit()
            
            # Also save to ChromaDB
            if self.chroma and self.user_facts_collection is not None:
                queued = self._queue_chroma_add(
                    self.user_facts_collection,
                    fact_id,
                    fact,
                    {
                        "user_id": user_id,
                        "category": category,
                        "confidence": confidence,
                    },
                )
                if not queued:
                    logger.warning("Dato guardado en SQLite; ChromaDB no pudo aceptar el índice")
            
            return fact_id
        except Exception as e:
            logger.error(f"Error saving user fact: {e}")
            return fact_id
    
    async def get_user_facts(self, user_id: str) -> list[dict]:
        """Get all known facts about a user."""
        try:
            if not self._db_connection:
                return []
            
            cursor = self._db_connection.cursor()
            cursor.execute("""
                SELECT id, fact, category, confidence
                FROM user_facts
                WHERE user_id = ?
                ORDER BY created_at DESC
            """, (user_id,))
            
            rows = cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "fact": row[1],
                    "category": row[2],
                    "confidence": row[3],
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Error getting user facts: {e}")
            return []
    
    async def clear_conversation(self, conversation_id: str):
        """Clear all messages in a conversation."""
        try:
            if self._db_connection:
                cursor = self._db_connection.cursor()
                cursor.execute("""
                    DELETE FROM messages
                    WHERE conversation_id = ?
                """, (conversation_id,))
                self._db_connection.commit()
        except Exception as e:
            logger.error(f"Error clearing conversation: {e}")

    # ==================== AFFECTION SYSTEM ====================
    
    async def get_affection(self, user_id: str) -> int:
        """Get affection score for a user (0-5). Default is 3."""
        try:
            if not self._db_connection:
                return 3
                
            cursor = self._db_connection.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS affection (
                    user_id TEXT PRIMARY KEY,
                    score INTEGER DEFAULT 3,
                    updated_at TEXT
                )
            """)
            
            cursor.execute("SELECT score FROM affection WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            
            if row:
                return max(0, min(5, row[0]))
            return 3
        except Exception as e:
            logger.error(f"Error getting affection: {e}")
            return 3

    async def update_affection(self, user_id: str, delta: int) -> int:
        """Update affection score. delta can be positive or negative."""
        try:
            if not self._db_connection:
                return 3
                
            cursor = self._db_connection.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS affection (
                    user_id TEXT PRIMARY KEY,
                    score INTEGER DEFAULT 3,
                    updated_at TEXT
                )
            """)
            
            current = await self.get_affection(user_id)
            new_score = max(0, min(5, current + delta))
            
            cursor.execute("""
                INSERT INTO affection (user_id, score, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    score = excluded.score,
                    updated_at = excluded.updated_at
            """, (user_id, new_score, datetime.now().isoformat()))
            
            self._db_connection.commit()
            
            logger.info(f"Affection updated for {user_id}: {current} → {new_score}")
            return new_score
        except Exception as e:
            logger.error(f"Error updating affection: {e}")
            return 3

