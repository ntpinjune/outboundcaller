# CLI vs Python Script: Key Differences

## The CLI Command

```bash
lk dispatch create --new-room --agent-name outbound-caller-dev --metadata '{"phone_number": "+12095539289"}'
```

## The Python Script

```python
payload = {
    "job": {
        "agent_name": "outbound-caller-dev",
        "room_name": "",
        "metadata": json.dumps(metadata)
    }
}
```

## Key Differences

### 1. **Room Creation**
- **CLI**: `--new-room` flag explicitly tells LiveKit to create a new room
- **Python**: `room_name: ""` (empty string) should also create a new room, but might be handled differently

### 2. **Authentication**
- **CLI**: Uses your LiveKit Cloud credentials automatically (from `lk login`)
- **Python**: Manually generates JWT token (should work the same, but more complex)

### 3. **Error Handling**
- **CLI**: Better error messages and validation
- **Python**: Basic error handling, might miss some edge cases

### 4. **Metadata Format**
- **CLI**: Direct JSON string in command
- **Python**: Uses `json.dumps()` which should be the same

## Why CLI Might Work Better

1. **Better Connection**: CLI might handle connection/authentication more reliably
2. **Room Handling**: `--new-room` might be more explicit than empty string
3. **Validation**: CLI validates parameters before sending
4. **Error Messages**: Better error reporting

## Solution: Use CLI in Python Script

You can actually call the CLI from Python! Update your script to use the CLI:

```python
import subprocess

def dispatch_to_livekit_cli(row_data: Dict[str, Any]) -> Optional[str]:
    """Dispatch using LiveKit CLI (more reliable)."""
    phone_number = normalize_phone_number(row_data["phone_number"])
    
    metadata = {
        "phone_number": phone_number,
        "name": row_data["name"],
        "appointment_time": row_data.get("appointment_time", ""),
        "row_id": str(row_data["row_number"])
    }
    
    cmd = [
        "lk", "dispatch", "create",
        "--new-room",
        "--agent-name", "outbound-caller-dev",
        "--metadata", json.dumps(metadata)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            logger.info(f"✅ Successfully dispatched call to {phone_number}")
            return "created"
        else:
            logger.error(f"❌ CLI error: {result.stderr}")
            return None
    except Exception as e:
        logger.error(f"❌ Error running CLI: {e}")
        return None
```

## Or: Fix the Python Script

The Python script should work the same way. The issue is likely:
1. Agent not receiving jobs (check logs)
2. Missing environment variables in cloud
3. SIP trunk not configured

Both methods should work - the CLI just has better error handling and validation.


