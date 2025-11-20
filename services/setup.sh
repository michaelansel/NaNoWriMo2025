#!/bin/bash
# Setup script for continuity webhook service

set -e

echo "=== Continuity Webhook Service Setup ==="
echo ""

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not found"
    exit 1
fi

# Create virtual environment if it doesn't exist
VENV_DIR="$(dirname "$0")/venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    echo "✓ Created virtual environment: $VENV_DIR"
else
    echo "✓ Virtual environment already exists: $VENV_DIR"
fi

# Install dependencies
echo "Installing Python dependencies..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r "$(dirname "$0")/requirements.txt"
echo "✓ Installed dependencies (flask, requests, PyJWT, cryptography, gunicorn)"

# Create config directory
CONFIG_DIR="$HOME/.config/continuity-webhook"
mkdir -p "$CONFIG_DIR"
echo "✓ Created config directory: $CONFIG_DIR"

# Generate webhook secret if not exists
ENV_FILE="$CONFIG_DIR/env"

if [ -f "$ENV_FILE" ]; then
    echo "⚠️  Environment file already exists at $ENV_FILE"
    read -p "Do you want to regenerate it? (y/N): " REGENERATE
    if [ "$REGENERATE" != "y" ] && [ "$REGENERATE" != "Y" ]; then
        echo "Keeping existing environment file"
        exit 0
    fi
fi

# Generate webhook secret
WEBHOOK_SECRET=$(openssl rand -hex 32)

# Prompt for GitHub token
echo ""
echo "GitHub Personal Access Token is required."
echo "Generate one at: https://github.com/settings/tokens"
echo "Required permissions: repo (full access)"
echo ""
read -p "Enter your GitHub token (ghp_...): " GITHUB_TOKEN

# Validate token format
if [[ ! "$GITHUB_TOKEN" =~ ^ghp_ ]]; then
    echo "⚠️  Warning: Token doesn't start with 'ghp_', this may not be a valid personal access token"
fi

# Write environment file
cat > "$ENV_FILE" <<EOF
# Environment variables for continuity-webhook service
# Generated on $(date)

# GitHub Personal Access Token
GITHUB_TOKEN=$GITHUB_TOKEN

# Webhook secret (share this with GitHub webhook configuration)
WEBHOOK_SECRET=$WEBHOOK_SECRET

# Repository information
REPO_OWNER=michaelansel
REPO_NAME=NaNoWriMo2025

# Port for webhook service
WEBHOOK_PORT=5000
EOF

chmod 600 "$ENV_FILE"
echo "✓ Created environment file: $ENV_FILE"
echo ""
echo "📝 IMPORTANT: Save this webhook secret for GitHub configuration:"
echo ""
echo "   $WEBHOOK_SECRET"
echo ""
echo "You'll need to add this to your GitHub webhook settings."

# Install systemd user service
echo ""
echo "Installing systemd user service..."

USER_SERVICE_DIR="$HOME/.config/systemd/user"
mkdir -p "$USER_SERVICE_DIR"

# Create systemd service file
SERVICE_FILE="$USER_SERVICE_DIR/continuity-webhook.service"
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Story Continuity Webhook Service
After=network.target

[Service]
Type=simple
WorkingDirectory=$HOME/Code/NaNoWriMo2025
EnvironmentFile=%h/.config/continuity-webhook/env
ExecStart=$VENV_DIR/bin/gunicorn --workers 4 --bind 0.0.0.0:5000 --chdir $HOME/Code/NaNoWriMo2025/services --timeout 180 --access-logfile - --error-logfile - continuity-webhook:app
Restart=always
RestartSec=10

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=continuity-webhook

[Install]
WantedBy=default.target
EOF

echo "✓ Installed service file: $SERVICE_FILE"

# Reload systemd
systemctl --user daemon-reload
echo "✓ Reloaded systemd"

# Enable service
systemctl --user enable continuity-webhook.service
echo "✓ Enabled service to start on boot"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "To start the service:"
echo "  systemctl --user start continuity-webhook"
echo ""
echo "To check status:"
echo "  systemctl --user status continuity-webhook"
echo ""
echo "To view logs:"
echo "  journalctl --user -u continuity-webhook -f"
echo ""
echo "Next steps:"
echo "1. Start the service: systemctl --user start continuity-webhook"
echo "2. Configure HTTPS/reverse proxy (nginx/caddy)"
echo "3. Open firewall port"
echo "4. Add webhook to GitHub repository settings"
echo "   - URL: https://your-server.com/webhook"
echo "   - Secret: $WEBHOOK_SECRET"
echo "   - Events: Workflow runs"
