# n8n + Google Sheets Integration Guide

This guide shows you how to set up n8n to read data from Google Sheets and dispatch calls to your LiveKit agent.

## Architecture Overview

```
Google Sheets → n8n Workflow → LiveKit API → Your Agent → Phone Call
```

1. **Google Sheets**: Stores customer data (name, phone, appointment time, etc.)
2. **n8n Workflow**: Reads from Google Sheets and dispatches agent jobs
3. **LiveKit API**: Receives dispatch request and starts the agent
4. **Your Agent**: Makes the phone call with personalized data

## Google Sheets Structure

Create a Google Sheet with these columns:

| Name        | Phone Number | Appointment Time    | Transfer To | Status  | Notes            |
| ----------- | ------------ | ------------------- | ----------- | ------- | ---------------- |
| John Doe    | +1234567890  | Next Tuesday at 3pm | +1987654321 | Pending | Existing patient |
| Jane Smith  | +1987654321  | Tomorrow at 2pm     | +1987654321 | Pending | New appointment  |
| Bob Johnson | +1555123456  |                     | +1987654321 | Pending | Follow-up call   |

**Column Descriptions:**

- **Name**: Customer's name (used for personalized greeting)
- **Phone Number**: Number to call (required)
- **Appointment Time**: Existing appointment if applicable (optional)
- **Transfer To**: Number to transfer to if requested (optional)
- **Status**: Track call status (Pending, Completed, Failed, etc.)
- **Notes**: Any additional information

## n8n Workflow Setup

### Step 1: Create New Workflow

1. Open n8n
2. Create a new workflow
3. Name it "LiveKit Agent Dispatcher"

### Step 2: Add Google Sheets Trigger

1. Add **Google Sheets** node
2. Choose **"Read Rows"** operation
3. Configure:
   - **Spreadsheet ID**: Your Google Sheet ID
   - **Sheet Name**: Your sheet name
   - **Range**: `A2:F100` (adjust based on your data)
   - **Options**:
     - Enable "Use First Row as Headers"
     - Enable "Continue on Error"

### Step 3: Filter Rows (Optional)

Add a **Filter** node to only process rows where:

- Status = "Pending"
- Phone Number is not empty

### Step 4: Transform Data

Add a **Code** node to format the data for LiveKit:

```javascript
// Transform Google Sheets row to LiveKit metadata format
const row = $input.item.json;

return {
  json: {
    phone_number: row["Phone Number"] || row.phone_number,
    name: row["Name"] || row.name || "Customer",
    appointment_time: row["Appointment Time"] || row.appointment_time || "",
    transfer_to: row["Transfer To"] || row.transfer_to || "",
    row_id: row.__rowNumber || row.id, // For updating status later
    notes: row["Notes"] || row.notes || "",
  },
};
```

### Step 5: Dispatch to LiveKit

Add an **HTTP Request** node:

**Method**: POST
**URL**: `https://{{LIVEKIT_URL}}/twirp/livekit.AgentService/CreateJob`

**Authentication**:

- Type: Header Auth
- Name: `Authorization`
- Value: `Bearer {{LIVEKIT_API_KEY}}:{{LIVEKIT_API_SECRET}}` (base64 encoded)

**Headers**:

```
Content-Type: application/json
```

**Body (JSON)**:

```json
{
  "job": {
    "agent_name": "outbound-caller-dev",
    "room_name": "",
    "metadata": "{{ $json }}"
  }
}
```

**Note**: The metadata should be a JSON string. In n8n, use:

```json
{
  "job": {
    "agent_name": "outbound-caller-dev",
    "room_name": "",
    "metadata": "{\"phone_number\": \"{{ $json.phone_number }}\", \"name\": \"{{ $json.name }}\", \"appointment_time\": \"{{ $json.appointment_time }}\", \"transfer_to\": \"{{ $json.transfer_to }}\"}"
  }
}
```

### Step 6: Update Google Sheets Status

Add another **Google Sheets** node to update the status:

1. Choose **"Update Row"** operation
2. Configure:
   - **Spreadsheet ID**: Same as before
   - **Sheet Name**: Same as before
   - **Row Number**: `{{ $json.row_id }}`
   - **Values**:
     - Status: "Dispatched" or "Completed"
     - Last Called: Current timestamp

### Step 7: Error Handling

Add an **Error Trigger** node to catch failures and update status to "Failed"

## Alternative: Using LiveKit CLI from n8n

Instead of HTTP Request, you can use **Execute Command** node:

```bash
lk dispatch create \
  --new-room \
  --agent-name outbound-caller-dev \
  --metadata '{"phone_number": "{{ $json.phone_number }}", "name": "{{ $json.name }}", "appointment_time": "{{ $json.appointment_time }}", "transfer_to": "{{ $json.transfer_to }}"}'
```

## Workflow Triggers

You can trigger the workflow in several ways:

### Option 1: Manual Trigger

- Click "Execute Workflow" button
- Processes all pending rows

### Option 2: Schedule Trigger

- Add **Cron** node
- Run every hour/day to process new rows

### Option 3: Webhook Trigger

- Add **Webhook** node
- Call from external system when new data is added

### Option 4: Google Sheets Webhook

- Use Google Apps Script to trigger n8n webhook when sheet is updated

## Environment Variables in n8n

Set these in n8n settings or use n8n's credential system:

- `LIVEKIT_URL`: Your LiveKit server URL
- `LIVEKIT_API_KEY`: Your LiveKit API key
- `LIVEKIT_API_SECRET`: Your LiveKit API secret

## Example n8n Workflow JSON

Here's a complete workflow you can import:

```json
{
  "name": "LiveKit Agent Dispatcher",
  "nodes": [
    {
      "parameters": {
        "operation": "read",
        "spreadsheetId": "YOUR_SHEET_ID",
        "sheetName": "Sheet1",
        "range": "A2:F100"
      },
      "name": "Read Google Sheets",
      "type": "n8n-nodes-base.googleSheets",
      "position": [250, 300]
    },
    {
      "parameters": {
        "conditions": {
          "string": [
            {
              "value1": "={{ $json.Status }}",
              "operation": "equals",
              "value2": "Pending"
            }
          ]
        }
      },
      "name": "Filter Pending",
      "type": "n8n-nodes-base.filter",
      "position": [450, 300]
    },
    {
      "parameters": {
        "jsCode": "const row = $input.item.json;\nreturn {\n  json: {\n    phone_number: row['Phone Number'],\n    name: row['Name'] || 'Customer',\n    appointment_time: row['Appointment Time'] || '',\n    transfer_to: row['Transfer To'] || '',\n    row_id: row.__rowNumber\n  }\n};"
      },
      "name": "Transform Data",
      "type": "n8n-nodes-base.code",
      "position": [650, 300]
    },
    {
      "parameters": {
        "method": "POST",
        "url": "={{ $env.LIVEKIT_URL }}/twirp/livekit.AgentService/CreateJob",
        "authentication": "headerAuth",
        "headerAuth": {
          "name": "Authorization",
          "value": "Bearer {{ $env.LIVEKIT_API_KEY }}:{{ $env.LIVEKIT_API_SECRET }}"
        },
        "jsonParameters": true,
        "bodyParametersJson": "={\n  \"job\": {\n    \"agent_name\": \"outbound-caller-dev\",\n    \"room_name\": \"\",\n    \"metadata\": JSON.stringify($json)\n  }\n}"
      },
      "name": "Dispatch to LiveKit",
      "type": "n8n-nodes-base.httpRequest",
      "position": [850, 300]
    }
  ],
  "connections": {
    "Read Google Sheets": {
      "main": [[{ "node": "Filter Pending", "type": "main", "index": 0 }]]
    },
    "Filter Pending": {
      "main": [[{ "node": "Transform Data", "type": "main", "index": 0 }]]
    },
    "Transform Data": {
      "main": [[{ "node": "Dispatch to LiveKit", "type": "main", "index": 0 }]]
    }
  }
}
```

## Testing

1. Add a test row to your Google Sheet with Status = "Pending"
2. Run the n8n workflow manually
3. Check LiveKit logs to see if the job was created
4. Verify the agent receives the correct metadata

## Workflow 2: Schedule Appointment Webhook

This webhook receives appointment scheduling requests from the agent.

**Webhook Configuration**:

- **Method**: POST
- **URL**: Your Make.com webhook URL (set as `MAKE_COM_WEBHOOK_URL`)

**Expected Data**:

```json
{
  "email": "patient@example.com",
  "name": "John Doe",
  "phone": "+1234567890",
  "appointment_time": "2024-12-31T14:00:00",
  "appointment_time_display": "02:00 PM on Tuesday, December 31, 2024",
  "time_description": "tomorrow at 2pm",
  "summary": "Appointment with John Doe",
  "source": "voice_agent",
  "caller_id": "+1234567890",
  "row_id": "123"
}
```

**Make.com Actions**:

1. Create Google Calendar event
2. Send email with calendar invite
3. Optionally return `meet_link` in response

## Workflow 3: Call Results Webhook

This webhook receives call results and transcripts from the agent after each call.

**Webhook Configuration**:

- **Method**: POST
- **URL**: Your Make.com webhook URL (set as `MAKE_COM_CALL_RESULTS_WEBHOOK_URL`)

**Expected Data**:

```json
{
  "phone_number": "+1234567890",
  "name": "John Doe",
  "call_status": "completed",
  "call_duration_seconds": 120,
  "transcript": "Agent: Hello...\nUser: Hi...",
  "appointment_scheduled": true,
  "appointment_time": "2024-12-31T14:00:00",
  "appointment_email": "patient@example.com",
  "timestamp": "2024-12-30T10:00:00Z",
  "row_id": "123"
}
```

**Call Status Values**:

- `completed` - Call completed successfully
- `voicemail` - Reached voicemail
- `failed` - Call failed or ended unexpectedly
- `no_answer` - No answer (if detected)

**Make.com Actions**:

1. Find Google Sheets row by `row_id` or `phone_number`
2. Update row with:
   - **Status**: Set to call_status (Completed, Voicemail, Failed, etc.)
   - **Transcript**: Full conversation transcript
   - **Appointment Scheduled**: Yes/No
   - **Appointment Time Scheduled**: ISO timestamp if scheduled
   - **Appointment Email**: Email used for calendar invite
   - **Call Duration**: Duration in seconds
   - **Last Called**: Current timestamp

## Google Sheets Structure

Recommended columns for your Google Sheet:

| Column Name                | Type         | Description                                    |
| -------------------------- | ------------ | ---------------------------------------------- |
| Phone Number               | Input        | Required - Phone number to call                |
| Name                       | Input        | Required - Customer name                       |
| Appointment Time           | Input        | Optional - Existing appointment if applicable  |
| Transfer To                | Input        | Optional - Number to transfer to               |
| Status                     | Output       | Pending → Completed/Failed/Voicemail/No Answer |
| Transcript                 | Output       | Full conversation transcript                   |
| Appointment Scheduled      | Output       | Yes/No                                         |
| Appointment Time Scheduled | Output       | ISO format timestamp                           |
| Appointment Email          | Output       | Email address used for calendar invite         |
| Call Duration              | Output       | Duration in seconds                            |
| Last Called                | Output       | Timestamp of last call attempt                 |
| Notes                      | Input/Output | Additional information                         |
| Row ID                     | Hidden       | For linking (can use row number)               |

## Complete Workflow Summary

### Workflow 1: Dispatch Calls from Google Sheets

1. **Trigger**: Manual, Schedule, or Webhook
2. **Read Google Sheets**: Get rows with Status = "Pending"
3. **Filter**: Only process valid phone numbers
4. **Transform**: Format data for LiveKit metadata
5. **Dispatch**: Send to LiveKit API with `row_id` in metadata

### Workflow 2: Schedule Appointments

1. **Webhook Trigger**: Receives appointment data from agent
2. **Create Google Calendar Event**: With Google Meet link
3. **Send Email**: Calendar invite to user's email
4. **Return Confirmation**: Optional meet_link in response

### Workflow 3: Update Google Sheets with Call Results

1. **Webhook Trigger**: Receives call results from agent
2. **Find Row**: Using `row_id` or `phone_number`
3. **Update Google Sheets**: Write transcript, status, appointment info
4. **Optional**: Send notifications or trigger follow-up actions

## Environment Variables

Add these to your `.env.local` file:

```bash
# Existing
MAKE_COM_WEBHOOK_URL=https://hook.us1.make.com/your-appointment-webhook-url

# New - for call results
MAKE_COM_CALL_RESULTS_WEBHOOK_URL=https://hook.us1.make.com/your-call-results-webhook-url
```

## Troubleshooting

- **Metadata not parsing**: Ensure metadata is a valid JSON string
- **Authentication errors**: Check your LiveKit API credentials
- **Agent not starting**: Verify agent_name matches your worker configuration
- **Missing data**: Check that Google Sheets columns match expected names
- **Transcript not captured**: Check that event listeners are properly registered
- **Call results not sent**: Verify `MAKE_COM_CALL_RESULTS_WEBHOOK_URL` is set
- **Double results sent**: Check that `hangup()` and session close handler don't both send

## Next Steps

1. Set up Google Sheet with your customer data (use recommended column structure)
2. Create n8n workflow 1: Read Google Sheets → Dispatch to LiveKit
3. Create n8n workflow 2: Schedule Appointment Webhook (if not already done)
4. Create n8n workflow 3: Call Results Webhook → Update Google Sheets
5. Set environment variables in `.env.local`
6. Test with a single row
7. Schedule or trigger workflow as needed
8. Monitor status updates in Google Sheets
