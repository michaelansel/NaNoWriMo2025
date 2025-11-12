# Story Continuity Webhook Service

This service receives GitHub webhooks when PR workflows complete, downloads story path artifacts, runs AI-based continuity checking using Ollama, and posts results back to the PR.

## Architecture

```
GitHub Actions (hosted runner)
  ↓ Build story paths
  ↓ Upload artifacts
  ↓ Workflow completes
  ↓ GitHub sends webhook
  ↓
Webhook Service (this host)
  ↓ Verify signature
  ↓ Download artifacts
  ↓ Run AI continuity check
  ↓ Post results to PR
```

## Security

- **No code execution from PRs**: Only text files (story content) are processed
- **Webhook signature verification**: HMAC-SHA256 signatures prevent spoofing
- **Artifact validation**: File structure and sizes are validated before processing
- **Text-only processing**: Story text goes to Ollama prompt only (never executed)

## Components

### 1. Webhook Service (`continuity-webhook.py`)
Flask web service that:
- Listens for GitHub `workflow_run` webhooks
- Verifies webhook signatures
- Downloads artifacts from completed workflows
- Calls AI checker script
- Posts formatted results to PRs

### 2. AI Checker Script (`../scripts/check-story-continuity.py`)
Python script that:
- Loads validation cache
- Identifies new/unvalidated story paths
- Sends each path to Ollama for analysis
- Returns structured results
- Updates validation cache

## Setup

### Prerequisites

- Python 3.12+
- Ollama installed with `gpt-oss:20b-fullcontext` model
- GitHub Personal Access Token with `repo` scope
- Server with HTTPS capability

### Installation

1. **Run setup script:**
   ```bash
   cd services
   ./setup.sh
   ```

   This will:
   - Create config directory (`~/.config/continuity-webhook/`)
   - Generate webhook secret
   - Prompt for GitHub token
   - Create environment file
   - Install systemd service

2. **Start the service:**
   ```bash
   sudo systemctl start continuity-webhook
   sudo systemctl status continuity-webhook
   ```

3. **View logs:**
   ```bash
   sudo journalctl -u continuity-webhook -f
   ```

### HTTPS Setup

The webhook service needs to be accessible via HTTPS. You have several options:

#### Option A: Nginx Reverse Proxy

```nginx
server {
    listen 443 ssl;
    server_name your-server.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location /webhook {
        proxy_pass http://localhost:5000/webhook;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

#### Option B: Caddy (Automatic HTTPS)

```caddy
your-server.com {
    reverse_proxy /webhook localhost:5000
}
```

## GitHub Configuration

### 1. Update Workflow

Modify `.github/workflows/build-and-deploy.yml` to upload allpaths artifacts:

```yaml
- name: Upload allpaths artifacts
  if: github.event_name == 'pull_request'
  uses: actions/upload-artifact@v3
  with:
    name: allpaths
    path: |
      dist/allpaths-text/
      dist/allpaths-validation-cache.json
    retention-days: 7
```

### 2. Configure Webhook

Go to repository settings → Webhooks → Add webhook:

- **Payload URL**: `https://your-server.com/webhook`
- **Content type**: `application/json`
- **Secret**: (use the secret from setup.sh output)
- **Events**: Select "Workflow runs"
- **Active**: ✓

## Testing

### Test 1: Health Check

```bash
curl http://localhost:5000/health
```

Expected output:
```json
{
  "status": "ok",
  "github_token_set": true,
  "webhook_secret_set": true,
  "checker_script_exists": true
}
```

### Test 2: Local AI Check

Test the AI checking script directly:

```bash
cd /home/ubuntu/Code/NaNoWriMo2025
python3 scripts/check-story-continuity.py dist/allpaths-text dist/allpaths-validation-cache.json
```

This should process any unvalidated paths and output results.

### Test 3: Simulate Webhook (Local)

Create a test payload and send it to the webhook:

```bash
# Generate test signature
WEBHOOK_SECRET="your_secret_here"
PAYLOAD='{"action":"completed","workflow_run":{"id":123,"event":"pull_request","conclusion":"success"}}'
SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" | sed 's/^.* //')

# Send webhook
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: workflow_run" \
  -H "X-Hub-Signature-256: sha256=$SIGNATURE" \
  -d "$PAYLOAD"
```

### Test 4: Live Test with PR

1. Create a test branch and modify a story passage
2. Open a PR
3. Wait for workflow to complete
4. Check service logs: `sudo journalctl -u continuity-webhook -f`
5. Verify comment appears on PR with continuity check results

## Troubleshooting

### Service won't start

```bash
# Check service status
sudo systemctl status continuity-webhook

# Check logs
sudo journalctl -u continuity-webhook -n 50

# Verify environment file
cat ~/.config/continuity-webhook/env
```

### Webhook signature verification fails

- Ensure webhook secret matches in GitHub and environment file
- Check nginx/proxy preserves X-Hub-Signature-256 header

### Ollama errors

```bash
# Test ollama directly
ollama run gpt-oss:20b-fullcontext "Hello"

# Check if model is available
ollama list
```

### Can't download artifacts

- Verify GitHub token has `repo` scope
- Check token expiration
- Ensure workflow uploaded artifacts with name "allpaths"

## Monitoring

### Service Status

```bash
sudo systemctl status continuity-webhook
```

### Recent Logs

```bash
sudo journalctl -u continuity-webhook -n 100
```

### Follow Logs

```bash
sudo journalctl -u continuity-webhook -f
```

### Restart Service

```bash
sudo systemctl restart continuity-webhook
```

## Configuration

Environment variables (in `~/.config/continuity-webhook/env`):

- `GITHUB_TOKEN`: GitHub Personal Access Token with repo scope
- `WEBHOOK_SECRET`: Secret for webhook signature verification
- `REPO_OWNER`: Repository owner (default: michaelansel)
- `REPO_NAME`: Repository name (default: NaNoWriMo2025)
- `WEBHOOK_PORT`: Port for service (default: 5000)

## Development

### Running Without Systemd

For development/testing:

```bash
cd services
source venv/bin/activate

# Set environment variables
export GITHUB_TOKEN="ghp_..."
export WEBHOOK_SECRET="..."
export REPO_OWNER="michaelansel"
export REPO_NAME="NaNoWriMo2025"
export WEBHOOK_PORT="5000"

# Run service
python3 continuity-webhook.py
```

### Making Changes

1. Modify code
2. Restart service: `sudo systemctl restart continuity-webhook`
3. Check logs: `sudo journalctl -u continuity-webhook -f`

## Security Considerations

- Keep `GITHUB_TOKEN` and `WEBHOOK_SECRET` secret
- Environment file has 600 permissions (owner read/write only)
- Service runs as `ubuntu` user (not root)
- Always verify webhook signatures in production
- Validate all artifact contents before processing
- Never execute code from artifacts (text processing only)

## Performance

- Ollama can take 30-120 seconds per path (model-dependent)
- Service has 10-minute timeout for AI checking
- Webhook responses are returned immediately (processing is async)
- Failed checks don't block PRs (warnings only)

## Maintenance

### Update Dependencies

```bash
cd services
source venv/bin/activate
pip install --upgrade flask requests
```

### Rotate Secrets

1. Generate new webhook secret: `openssl rand -hex 32`
2. Update `~/.config/continuity-webhook/env`
3. Update GitHub webhook settings
4. Restart service: `sudo systemctl restart continuity-webhook`

### Backup Configuration

```bash
cp ~/.config/continuity-webhook/env ~/continuity-webhook-env.backup
```

## Future Enhancements

Potential improvements:
- Queue system for parallel processing multiple PRs
- Web dashboard for viewing check history
- Configurable prompts via config file
- Support for multiple models/providers
- Fine-tuning prompt based on feedback
- Integration with GitHub status checks
\n# Testing webhook with async processing
