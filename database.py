
import sqlite3
import csv
import io
from datetime import datetime
from typing import List, Dict, Any, Optional

DB_FILE = "leads.db"

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the leads table."""
    conn = get_db()
    c = conn.cursor()
    
    # Create the table with the full schema
    c.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT NOT NULL,
            name TEXT,
            status TEXT DEFAULT 'Pending',
            appointment_scheduled TEXT,
            appointment_time_scheduled TEXT,
            appointment_email TEXT,
            transcript TEXT,
            call_duration TEXT,
            last_called TEXT,
            business_name TEXT,
            room_name TEXT,
            session_id TEXT,
            outcome_details TEXT,
            retry_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Migration: Add missing columns if they don't exist
    required_columns = [
        ("status", "TEXT DEFAULT 'Pending'"),
        ("appointment_scheduled", "TEXT"),
        ("appointment_time_scheduled", "TEXT"),
        ("appointment_email", "TEXT"),
        ("transcript", "TEXT"),
        ("call_duration", "TEXT"),
        ("last_called", "TEXT"),
        ("business_name", "TEXT"),
        ("room_name", "TEXT"),
        ("session_id", "TEXT"),
        ("outcome_details", "TEXT")
    ]
    
    c.execute("PRAGMA table_info(leads)")
    existing_columns = [row[1] for row in c.fetchall()]
    
    for col_name, col_type in required_columns:
        if col_name not in existing_columns:
            try:
                c.execute(f"ALTER TABLE leads ADD COLUMN {col_name} {col_type}")
            except Exception as e:
                print(f"Error adding column {col_name}: {e}")
                
    conn.commit()
    conn.close()

import logging
logger = logging.getLogger(__name__)

def import_csv_content(csv_content: str) -> int:
    """Import leads from CSV string content. Returns count of added rows."""
    if not csv_content.strip():
        logger.warning("Empty CSV content received")
        return 0
        
    conn = get_db()
    c = conn.cursor()
    
    # Try to detect delimiter (comma or tab)
    first_line = csv_content.split('\n')[0]
    delimiter = ','
    if '\t' in first_line and first_line.count('\t') > first_line.count(','):
        delimiter = '\t'
    
    logger.info(f"Importing CSV with delimiter: {repr(delimiter)}")
    
    # Parse CSV
    f = io.StringIO(csv_content)
    # Using list to allow multiple passes if needed for smart detection
    content_list = list(csv.DictReader(f, delimiter=delimiter))
    if not content_list:
        logger.warning("CSV parsed but no data rows found")
        return 0
        
    headers = list(content_list[0].keys())
    logger.info(f"CSV Headers detected: {headers}")
    
    # Mapping logic
    phone_col = None
    name_col = None
    business_col = None
    
    # 1. Try exact/common headers
    phone_variants = ["phone_number", "phone number", "phone", "number", "phonenumber", "cell", "mobile", "tel", "phone_no"]
    name_variants = ["name", "full name", "customer name"]
    business_variants = ["business_name", "business name", "business", "company", "company_name"]
    
    for h in headers:
        if not h: continue
        h_clean = h.strip().lower()
        if not phone_col and any(v in h_clean for v in phone_variants): phone_col = h
        if not name_col and any(v in h_clean for v in name_variants): name_col = h
        if not business_col and any(v in h_clean for v in business_variants): business_col = h

    # 2. Smart Detection: If we still don't have a phone column, scan rows for phone-like strings
    import re
    phone_pattern = re.compile(r'^\+?[\d\s\-\(\)\.]{7,20}$')
    
    if not phone_col:
        logger.info("Standard phone headers not found, starting smart detection...")
        for h in headers:
            if not h: continue
            # Check first 5 rows
            matches = 0
            for row in content_list[:5]:
                val = str(row.get(h, "")).strip()
                if phone_pattern.match(val) and any(c.isdigit() for c in val):
                    matches += 1
            if matches >= 2: # At least 2 matches in 5 rows
                logger.info(f"Smart detected phone column: {h}")
                phone_col = h
                break

    # 3. Import Rows
    count = 0
    for row in content_list:
        phone = str(row.get(phone_col, "") if phone_col else "").strip()
        if not phone or not any(c.isdigit() for c in phone):
            continue
            
        # Extract other fields with fallback
        def get_val(col_name, variants):
            if col_name: return row.get(col_name) or ""
            # Fallback to variant search
            row_map = {k.strip().lower(): k for k in row.keys() if k}
            for v in variants:
                if v in row_map: return row[row_map[v]] or ""
            return ""

        data = {
            "phone_number": phone,
            "name": get_val(name_col, ["Name", "Customer Name"]),
            "status": get_val(None, ["Status"]) or "Pending",
            "appointment_scheduled": get_val(None, ["Appointment Scheduled"]),
            "appointment_time_scheduled": get_val(None, ["Appointment Time Scheduled"]),
            "appointment_email": get_val(None, ["Appointment Email"]),
            "transcript": get_val(None, ["Transcript"]),
            "call_duration": get_val(None, ["Call_Duration", "duration"]),
            "last_called": get_val(None, ["Last Called"]),
            "business_name": get_val(business_col, ["Business_name", "business", "company"]),
            "room_name": get_val(None, ["Room_Name"]),
            "session_id": get_val(None, ["Session_ID"]),
            "outcome_details": get_val(None, ["Outcome_Details"])
        }
        
        c.execute('''
            INSERT INTO leads (
                phone_number, name, status, appointment_scheduled, 
                appointment_time_scheduled, appointment_email, transcript, 
                call_duration, last_called, business_name, room_name, 
                session_id, outcome_details
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data["phone_number"], data["name"], data["status"], data["appointment_scheduled"],
            data["appointment_time_scheduled"], data["appointment_email"], data["transcript"],
            data["call_duration"], data["last_called"], data["business_name"], data["room_name"],
            data["session_id"], data["outcome_details"]
        ))
        count += 1
        
    conn.commit()
    conn.close()
    logger.info(f"Successfully imported {count} leads from CSV")
    return count

def get_pending_leads(limit: int = 1000) -> List[Dict[str, Any]]:
    """Get pending leads."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM leads WHERE status = 'Pending' LIMIT ?", (limit,))
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows

def get_all_leads() -> List[Dict[str, Any]]:
    """Get all leads."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM leads ORDER BY id ASC")
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows

def update_lead_status(lead_id: int, status: str):
    """Update lead status."""
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('''
        UPDATE leads 
        SET status = ?, last_called = ? 
        WHERE id = ?
    ''', (status, now, lead_id))
    conn.commit()
    conn.close()

def get_lead_status(lead_id: int) -> Optional[str]:
    """Get status of a specific lead."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT status FROM leads WHERE id = ?", (lead_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def get_stats() -> Dict[str, int]:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT status, COUNT(*) FROM leads GROUP BY status")
    stats = {row[0]: row[1] for row in c.fetchall()}
    conn.close()
    return stats

def clear_leads():
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM leads")
    conn.commit()
    conn.close()
