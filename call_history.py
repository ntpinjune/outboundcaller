"""
Call History Database

SQLite-based storage for call records with transcripts and audio file references.
Provides a local observability layer independent of LiveKit Cloud.
"""

import sqlite3
import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger("call-history")

# Database file path
DB_PATH = os.path.join(os.path.dirname(__file__), "call_history.db")


@dataclass
class CallRecord:
    """Represents a single call record."""
    room_id: str
    phone_number: str
    name: str = ""
    status: str = "pending"  # pending, completed, voicemail, failed, no_answer, busy
    duration_seconds: int = 0
    transcript: str = ""
    audio_url: str = ""  # S3 URL or local path
    egress_id: str = ""  # LiveKit Egress ID
    metadata: str = ""  # JSON string for extra data
    created_at: str = ""
    updated_at: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CallRecord":
        """Create from dictionary."""
        # Filter to only include fields that exist in the dataclass
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)


class CallHistory:
    """SQLite-based call history storage."""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize the database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id TEXT UNIQUE NOT NULL,
                phone_number TEXT NOT NULL,
                name TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                duration_seconds INTEGER DEFAULT 0,
                transcript TEXT DEFAULT '',
                audio_url TEXT DEFAULT '',
                egress_id TEXT DEFAULT '',
                metadata TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # Create index for faster lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_calls_created_at ON calls(created_at DESC)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_calls_status ON calls(status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_calls_phone ON calls(phone_number)
        """)
        
        conn.commit()
        conn.close()
        logger.info(f"[OK] Call history database initialized: {self.db_path}")
    
    def save_call(self, record: CallRecord) -> bool:
        """Save or update a call record."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            now = datetime.now().isoformat()
            if not record.created_at:
                record.created_at = now
            record.updated_at = now
            
            # Upsert: insert or replace
            cursor.execute("""
                INSERT OR REPLACE INTO calls 
                (room_id, phone_number, name, status, duration_seconds, 
                 transcript, audio_url, egress_id, metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.room_id,
                record.phone_number,
                record.name,
                record.status,
                record.duration_seconds,
                record.transcript,
                record.audio_url,
                record.egress_id,
                record.metadata,
                record.created_at,
                record.updated_at
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"[OK] Saved call record: {record.room_id}")
            return True
        except Exception as e:
            logger.error(f"[ERROR] Failed to save call record: {e}")
            return False
    
    def get_call(self, room_id: str) -> Optional[CallRecord]:
        """Get a single call record by room ID."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM calls WHERE room_id = ?", (room_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return CallRecord.from_dict(dict(row))
            return None
        except Exception as e:
            logger.error(f"[ERROR] Failed to get call record: {e}")
            return None
    
    def get_calls(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
        phone_number: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> List[CallRecord]:
        """Get call records with optional filtering."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM calls WHERE 1=1"
            params = []
            
            if status:
                query += " AND status = ?"
                params.append(status)
            
            if phone_number:
                query += " AND phone_number LIKE ?"
                params.append(f"%{phone_number}%")
            
            if date_from:
                query += " AND created_at >= ?"
                params.append(date_from)
            
            if date_to:
                query += " AND created_at <= ?"
                params.append(date_to)
            
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
            
            return [CallRecord.from_dict(dict(row)) for row in rows]
        except Exception as e:
            logger.error(f"[ERROR] Failed to get call records: {e}")
            return []
    
    def get_call_count(self, status: Optional[str] = None) -> int:
        """Get total count of calls, optionally filtered by status."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if status:
                cursor.execute("SELECT COUNT(*) FROM calls WHERE status = ?", (status,))
            else:
                cursor.execute("SELECT COUNT(*) FROM calls")
            
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception as e:
            logger.error(f"[ERROR] Failed to get call count: {e}")
            return 0
    
    def delete_call(self, room_id: str) -> bool:
        """Delete a call record."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM calls WHERE room_id = ?", (room_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
            conn.close()
            return deleted
        except Exception as e:
            logger.error(f"[ERROR] Failed to delete call record: {e}")
            return False
    
    def update_call_status(self, room_id: str, status: str, **kwargs) -> bool:
        """Update call status and optionally other fields."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            updates = ["status = ?", "updated_at = ?"]
            params = [status, datetime.now().isoformat()]
            
            for key, value in kwargs.items():
                if key in ['duration_seconds', 'transcript', 'audio_url', 'egress_id', 'metadata']:
                    updates.append(f"{key} = ?")
                    params.append(value)
            
            params.append(room_id)
            query = f"UPDATE calls SET {', '.join(updates)} WHERE room_id = ?"
            
            cursor.execute(query, params)
            conn.commit()
            updated = cursor.rowcount > 0
            conn.close()
            return updated
        except Exception as e:
            logger.error(f"[ERROR] Failed to update call status: {e}")
            return False


# Singleton instance
_call_history: Optional[CallHistory] = None


def get_call_history() -> CallHistory:
    """Get the singleton CallHistory instance."""
    global _call_history
    if _call_history is None:
        _call_history = CallHistory()
    return _call_history


# Convenience functions
def save_call(record: CallRecord) -> bool:
    """Save a call record."""
    return get_call_history().save_call(record)


def get_call(room_id: str) -> Optional[CallRecord]:
    """Get a call record by room ID."""
    return get_call_history().get_call(room_id)


def get_calls(**kwargs) -> List[CallRecord]:
    """Get call records with optional filtering."""
    return get_call_history().get_calls(**kwargs)


def update_call_status(room_id: str, status: str, **kwargs) -> bool:
    """Update call status."""
    return get_call_history().update_call_status(room_id, status, **kwargs)


if __name__ == "__main__":
    # Test the module
    logging.basicConfig(level=logging.INFO)
    
    history = CallHistory()
    
    # Create a test record
    test_record = CallRecord(
        room_id="test-room-123",
        phone_number="+15551234567",
        name="Test Customer",
        status="completed",
        duration_seconds=120,
        transcript="Agent: Hello!\nCustomer: Hi there!",
    )
    
    # Save it
    history.save_call(test_record)
    
    # Retrieve it
    retrieved = history.get_call("test-room-123")
    if retrieved:
        print(f"Retrieved: {retrieved.name} - {retrieved.status}")
    
    # List all
    all_calls = history.get_calls()
    print(f"Total calls: {len(all_calls)}")
    
    # Cleanup test
    history.delete_call("test-room-123")
    print("Test completed!")
