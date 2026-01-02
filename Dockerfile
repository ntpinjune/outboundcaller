FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies (needed for some audio libraries)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Download required model files (if needed)
# Uncomment if your agent needs to download models:
# RUN python agent.py download-files

# Run the agent
CMD ["python", "agent.py", "start"]
