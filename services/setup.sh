#!/bin/bash
# Setup script for continuity webhook service

set -e

echo "=== Continuity Webhook Service Setup ==="
echo ""

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

# Install systemd service
echo ""
echo "Installing systemd service..."

SERVICE_FILE="/etc/systemd/system/continuity-webhook.service"
sudo cp "$(dirname "$0")/continuity-webhook.service" "$SERVICE_FILE"
echo "✓ Installed service file: $SERVICE_FILE"

# Reload systemd
sudo systemctl daemon-reload
echo "✓ Reloaded systemd"

# Enable service
sudo systemctl enable continuity-webhook.service
echo "✓ Enabled service to start on boot"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "To start the service:"
echo "  sudo systemctl start continuity-webhook"
echo ""
echo "To check status:"
echo "  sudo systemctl status continuity-webhook"
echo ""
echo "To view logs:"
echo "  sudo journalctl -u continuity-webhook -f"
echo ""
echo "Next steps:"
echo "1. Start the service: sudo systemctl start continuity-webhook"
echo "2. Configure HTTPS/reverse proxy (nginx/caddy)"
echo "3. Open firewall port"
echo "4. Add webhook to GitHub repository settings"
echo "   - URL: https://your-server.com/webhook"
echo "   - Secret: $WEBHOOK_SECRET"
echo "   - Events: Workflow runs"
