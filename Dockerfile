FROM python:3.11-slim

# Base workdir for the project
WORKDIR /app

# Install Python dependencies for the Synthetica swarm
COPY Synthetica-upstream/synthetica/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the full project into the container (includes Synthetica-upstream)
COPY . .

# Run agents from the Synthetica swarm package directory where main.py lives
WORKDIR /app/Synthetica-upstream/synthetica