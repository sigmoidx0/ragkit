#!/bin/bash
# EC2 user data (Amazon Linux 2023): install Docker, fetch ragkit, start the stack.
# Set the variables below before launching. Not run in an AWS account yet —
# the stack itself is verified locally with the same compose file.
set -euo pipefail

REPO_URL="https://github.com/sigmoidx0/ragkit.git"
LLM_PROVIDER="google"            # or leave empty and use --profile ollama below
LLM_MODEL="gemini-3.5-flash"
GOOGLE_API_KEY=""                # better: fetch from SSM Parameter Store

dnf install -y docker git
systemctl enable --now docker
mkdir -p /usr/local/lib/docker/cli-plugins
curl -fsSL "https://github.com/docker/compose/releases/download/v2.29.7/docker-compose-linux-$(uname -m)" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

git clone "$REPO_URL" /opt/ragkit
cd /opt/ragkit
cat > deploy/.env <<ENV
JWT_SECRET_KEY=$(openssl rand -hex 32)
INITIAL_ADMIN_PASSWORD=$(openssl rand -hex 12)
POSTGRES_PASSWORD=$(openssl rand -hex 16)
LLM_PROVIDER=${LLM_PROVIDER}
LLM_MODEL=${LLM_MODEL}
GOOGLE_API_KEY=${GOOGLE_API_KEY}
WEB_PORT=80
ENV
chmod 600 deploy/.env

# Ollama still serves embeddings, so the profile stays on even with a hosted chat model.
docker compose -f deploy/docker-compose.yml --profile ollama up -d --build
echo "admin password: $(grep INITIAL_ADMIN_PASSWORD deploy/.env | cut -d= -f2)" > /root/ragkit-admin.txt
