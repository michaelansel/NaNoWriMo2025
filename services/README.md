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
- Processes checks asynchronously in background threads
- Posts real-time progress updates to PRs as each path completes
- Posts final summary with all results
- Tracks active jobs and provides `/status` endpoint for monitoring

### 2. AI Checker Script (`../scripts/check-story-continuity.py`)
Python script that:
- Loads validation cache to track validated paths
- Identifies new/unvalidated story paths
- Sends each path to Ollama HTTP API for analysis
- Supports progress callbacks for real-time updates
- Returns structured results with detailed issue information
- Updates validation cache after each path

### 3. Progress Updates
The service posts three types of comments to PRs:

1. **Initial Comment**: Posted when checking starts, lists all paths to be validated
2. **Progress Updates**: Posted after each path completes with:
   - Path route and severity (none/minor/major/critical)
   - Summary of issues found
   - Detailed issue list in collapsible section (type, severity, description, location)
3. **Final Summary**: Comprehensive report organizing all issues by severity

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
   - Install Python dependencies (Flask, requests, gunicorn)
   - Install systemd service (configured to use Gunicorn WSGI server)

2. **Start the service:**
   ```bash
   systemctl --user start continuity-webhook
   systemctl --user status continuity-webhook
   systemctl --user enable continuity-webhook  # Auto-start on boot
   ```

3. **View logs:**
   ```bash
   journalctl --user -u continuity-webhook -f
   ```

Note: The service runs as a user systemd service (not system-wide) for better security and isolation.

### HTTPS Setup

The webhook service needs to be accessible via HTTPS. You have several options:

#### Option A: Nginx Reverse Proxy + Let's Encrypt

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
        proxy_pass_request_headers on;  # Preserve webhook signature
    }

    location /health {
        proxy_pass http://localhost:5000/health;
        proxy_set_header Host $host;
    }

    location /status {
        proxy_pass http://localhost:5000/status;
        proxy_set_header Host $host;
    }
}
```

For Let's Encrypt certificates:
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-server.com
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
  uses: actions/upload-artifact@v4
  with:
    name: story-preview
    path: |
      dist/
      allpaths-validation-status.json
    retention-days: 30
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

### Test 2: Status/Metrics Endpoint

```bash
curl http://localhost:5000/status
```

Expected output:
```json
{
  "active_job_count": 0,
  "active_jobs": [],
  "metrics": {
    "total_webhooks_received": 5,
    "total_paths_checked": 42,
    "total_jobs_completed": 3,
    "total_jobs_failed": 0
  },
  "recent_completed_jobs": [
    {
      "workflow_id": 123456,
      "pr_number": 42,
      "start_time": "2025-11-12T16:00:00",
      "status": "completed",
      "duration_seconds": 180.5,
      "total_paths": 14
    }
  ],
  "uptime_seconds": 3600
}
```

### Test 3: Local AI Check

Test the AI checking script directly:

```bash
cd /home/ubuntu/Code/NaNoWriMo2025
python3 scripts/check-story-continuity.py dist/allpaths-metadata allpaths-validation-status.json
```

This should process any unvalidated paths and output results.

### Test 4: Simulate Webhook (Local)

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

### Test 5: Live Test with PR

1. Create a test branch and modify a story passage
2. Open a PR
3. Wait for workflow to complete
4. Check service logs: `journalctl --user -u continuity-webhook -f`
5. Monitor status endpoint: `curl http://localhost:5000/status`
6. Verify comments appear on PR:
   - Initial comment with list of paths
   - Progress update for each path (with detailed issues)
   - Final summary with all results organized by severity

## Validation Modes

The continuity checker supports three validation modes to balance speed and thoroughness.

**For detailed product requirements and technical architecture, see:**
- [features/ai-continuity-checking.md](../features/ai-continuity-checking.md) - Product specification
- [architecture/002-validation-cache.md](../architecture/002-validation-cache.md) - Technical architecture and design decisions

### Quick Reference

**🆕 new-only (Default)** - Check only new paths

```
/check-continuity
```

**📝 modified** - Check new and modified paths

```
/check-continuity modified
```

**🔍 all** - Check all paths

```
/check-continuity all
```

### Understanding Path Categories

The checker categorizes paths as:
- **New:** Path never seen before (new story branch)
- **Modified:** Path content changed since last validation (hash changed)
- **Unchanged:** Path validated and no changes (same hash)

The content-based hash system automatically detects changes.

---

### Understanding Path Categorization (Detailed)

This section explains the detailed logic for how the continuity checker categorizes paths. **You don't need to understand this to use the feature** - just choose the appropriate validation mode. This is for writers who want to understand why certain paths are categorized certain ways.

**Critical Principle:** Categories are about **PATH EXISTENCE**, not file changes. The fundamental question is: "Did this route through the story exist before this PR?" NOT "Did file content change?"

**Key Terms:**
- **Path/Route:** A sequence of passages from Start to an ending. "Path" and "route" are used interchangeably - both refer to a specific journey a player can take through the story.
- **Novel prose:** New story content (narrative text, dialogue, descriptions) that has never been validated before. This does NOT include: formatting changes (smart quotes, spacing), navigation changes (adding/removing links), or reorganization of existing prose (passage splits, content moves).
- **Content change:** ANY modification to a passage file, including: prose edits, formatting, navigation (links), or structure. Much broader than "novel prose."

#### The Two-Level Test

The checker uses a two-level decision process:

1. **PRIMARY: Path Existence Test** - Did this exact sequence of passages exist in the base branch?
   - If YES → Path is either MODIFIED or UNCHANGED (never NEW)
   - If NO → Path is either NEW or MODIFIED (depends on prose novelty)

2. **SECONDARY: Content/Prose Test** - What changed?
   - If path existed: Did any passage content change? → MODIFIED or UNCHANGED
   - If path is new: Does it contain novel prose? → NEW or MODIFIED

**Decision Table:**

| Path existed before? | Contains novel prose? | Category | Reasoning |
|---------------------|----------------------|----------|-----------|
| YES | N/A (doesn't matter) | MODIFIED or UNCHANGED | Existing paths are never NEW, even if you added novel prose to them |
| YES | N/A | UNCHANGED | Path existed, no content changed in any passage |
| YES | N/A | MODIFIED | Path existed, at least one passage had content changes |
| NO | YES | NEW | New route with new story content needs first validation |
| NO | NO | MODIFIED | New route structure but prose was already validated (reorganization) |

#### NEW Paths (Internal Category)

**What it means:** This path did NOT exist before this PR AND contains novel prose (new story content never validated before).

**How to identify:**
1. Path existence test: Did this sequence of passages exist in base branch? → NO
2. Prose novelty test: Does it contain novel prose? → YES
3. Result: NEW

**What causes this:**
- Created new passage with new story content, and a path goes through it
- Added new link creating a path that didn't exist before, and that path includes novel prose
- Players can take a journey they couldn't before, reading prose they've never seen

**Example:** You create `KEB-251121.twee` with a new scene about discovering the cave. A path `Start → Forest → Cave → Victory` is NEW because:
1. This sequence didn't exist before (PATH test: NO)
2. The cave scene has novel prose (PROSE test: YES)
3. Result: NEW - needs first-time validation

**Why this matters:** NEW paths must be validated because they're routes with novel content that have never been reviewed.

#### MODIFIED Paths (Internal Category)

**What it means:** EITHER (Type A) this path existed before and content changed in at least one passage, OR (Type B) this path is new but contains no novel prose (reorganization).

**How to identify - Type A (Existing path with changes):**
1. Path existence test: Did this sequence exist in base branch? → YES
2. Content change test: Did any passage in the path change? → YES
3. Result: MODIFIED

**How to identify - Type B (New path, no novel prose):**
1. Path existence test: Did this sequence exist in base branch? → NO
2. Prose novelty test: Does it contain novel prose? → NO
3. Result: MODIFIED (reorganization case)

**What causes this:**
- **Type A:** Edited prose, formatting, or navigation in an existing path's passages
- **Type B:** Reorganized existing prose (passage splits, content moves) creating new navigation sequences

**Example 1 - Prose edits (Type A):**
Path `Start → Continue on → Village → End` existed before. You fix a typo in Village passage.
- PATH test: YES (existed before)
- CONTENT test: YES (Village changed)
- Result: MODIFIED

**Example 2 - Adding novel prose to existing path (Type A):**
Path `Start → Continue on → Village → End` existed before. You add a new paragraph with novel prose to Village.
- PATH test: YES (existed before) ← **This takes priority**
- Result: MODIFIED (path existed, so NEVER NEW even though prose is novel)

**Example 3 - Linter reformats files (Type A):**
Linter reformats 55 files (smart quotes, spacing). All paths through these files are MODIFIED.
- PATH test: YES (paths existed before)
- CONTENT test: YES (formatting changed)
- PROSE test: NO (prose not novel, just reformatted)
- Result: MODIFIED

**Example 4 - Passage split (Type B - CRITICAL CASE):**

**Before split:**
- Passage: `LongPassage` contains "First part. Second part."
- Path exists: `Start → LongPassage → End`

**After split:**
- `LongPassage` becomes "First part." with link `[[Continue→PartTwo]]`
- New passage `PartTwo` contains "Second part."
- Two paths now exist:
  1. `Start → LongPassage → PartTwo → End` (new sequence)
  2. `Start → LongPassage → End` (original sequence, but LongPassage changed)

**Analysis:**
- **New path** `Start → LongPassage → PartTwo → End`:
  - PATH test: NO (this sequence didn't exist before)
  - PROSE test: NO (prose from LongPassage, just reorganized)
  - Result: MODIFIED (Type B - reorganization)
- **Original path** `Start → LongPassage → End`:
  - PATH test: YES (this sequence existed before)
  - CONTENT test: YES (LongPassage changed - added link, removed prose)
  - Result: MODIFIED (Type A - existing path with changes)

**Why this matters:** MODIFIED paths may need re-validation because either the reading experience changed (Type A) or the navigation structure changed (Type B).

#### UNCHANGED Paths (Internal Category)

**What it means:** This path existed before this PR AND no passage in the path changed.

**How to identify:**
1. Path existence test: Did this sequence exist in base branch? → YES
2. Content change test: Did any passage in the path change? → NO
3. Result: UNCHANGED

**What causes this:**
- Made changes to other parts of the story
- This path doesn't include any passages you touched
- Path exists in both base and PR with identical content

**Example:** You add a new passage in one story branch. Paths in completely different branches are UNCHANGED:
- PATH test: YES (paths existed before)
- CONTENT test: NO (no passages in these paths changed)
- Result: UNCHANGED

**Why this matters:** UNCHANGED paths don't need re-validation - already validated, nothing changed.

#### Understanding the Distinction: Paths vs Files

**Common confusion:** "I changed 55 files, so I have 55 NEW paths, right?"

**No.** The question isn't "Did files change?" It's "Did these paths exist before?"

**Mental model:**
- Think of your story as a map with paths from START to various endings
- NEW = A path that wasn't on the map before AND contains novel prose
- MODIFIED = Either (A) a path that was on the map before and the journey changed, OR (B) a new path structure with no novel prose
- UNCHANGED = A path that was on the map before and the journey is identical

**Quick reference:**
- Linter reformats 55 files → All paths MODIFIED (existed before + content changed)
- Split passage into two → New path sequence MODIFIED (new structure + no novel prose), original path MODIFIED (existed before + content changed)
- Add novel prose to existing path → Path MODIFIED (existed before, so never NEW)
- Create new passage with novel prose → Paths through it are NEW (didn't exist + novel prose)

---

### Edge Cases (Categorization)

These edge cases relate to how paths are categorized. For general edge cases, see [features/ai-continuity-checking.md](../features/ai-continuity-checking.md#edge-cases).

#### Unreachable Paths

**Scenario:** A path becomes unreachable due to removed links, but still exists in the story structure

**Example:** You remove the link `[[Go to secret cave]]` from the Forest passage. The path `Start → Forest → SecretCave → End` still exists in the graph (all passages and links are present) but players can't reach it anymore.

**Behavior:**
- Path is categorized as MODIFIED (the Forest passage changed - link removed)
- Path is validated if in validation mode scope
- AI may flag that the path is unreachable
- Writers can approve path if unreachability is intentional (dead branch)
- Or fix by restoring link if unintentional

**Status:** Working as intended - categorization is about content changes, not reachability

#### Compound Changes

**Scenario:** A single PR makes multiple types of changes affecting the same path

**Example:** In one PR, you:
1. Fix typos in passage A (content change)
2. Add novel prose to passage B (content change with novel prose)
3. Add a new link in passage C (navigation change)
All three passages are part of path `Start → A → B → C → End`

**Question:** Is this path NEW or MODIFIED?

**Answer:**
- PATH test: Did `Start → A → B → C → End` exist before? → YES (sequence existed)
- Result: MODIFIED (path existed, so never NEW, even though passage B has novel prose)
- The novel prose in passage B doesn't make the path NEW because the path sequence already existed

**Behavior:**
- Path correctly categorized as MODIFIED
- Validation checks the entire path including the novel prose in passage B
- Single validation covers all changes

**Status:** Working as intended - PATH EXISTENCE test takes priority

---

### Recommended Workflow

1. **During development:** Automatic `new-only` mode (fast feedback)
2. **Before review:** `/check-continuity modified` (validate all changes)
3. **After refactoring:** `/check-continuity all` (full audit)
4. **After validation:** `/approve-path [ids]` (mark as reviewed)

**For complete documentation including use cases, examples, and design rationale, see the links above.**

## Approving Validated Paths

After reviewing AI feedback, you can mark paths as validated to skip them in future checks:

### How It Works

1. **Review AI feedback** on the PR (progress comments show individual path results)
2. **Reply to approve** paths you've reviewed:
   ```
   /approve-path abc12345 def67890 e4f5a678
   ```
3. **Service processes approval**:
   - Checks you're a repository collaborator
   - Downloads latest validation cache from PR artifacts
   - Marks paths as validated in cache
   - Commits updated cache to your PR branch
4. **Workflow runs** on the new commit
5. **Approved paths are skipped** - only new/unvalidated paths are checked

### Path ID Behavior

- **Content-based hashing**: Path IDs are 8-character hashes based on passage content
- **Automatic re-validation**: If you edit any passage in an approved path, the hash changes and it requires re-validation
- **Structure changes**: Renaming passages or changing path structure also changes the hash

### Batch Approval

Approve multiple paths in a single comment:
```
Great work! These all look good:
/approve-path a3f8b912 b2c7d843 f4e1a923 c9d2e144
```

The service extracts all 8-character hex hashes and processes them together in one commit.

### Authorization

Only repository collaborators can approve paths. If a non-collaborator tries to approve, they'll receive an error message.

### Example Workflow

**AI posts validation:**
```
### 🟢 Path 4/14 Complete
**Path ID:** `a3f8b912`
**Route:** `Start → Continue → Cave → Victory`
**Result:** minor
**Summary:** Small timeline inconsistency

💡 To approve this path: reply `/approve-path a3f8b912`
```

**You reply:**
```
Timeline issue is acceptable for the story flow.
/approve-path a3f8b912
```

**Service responds:**
```
✅ Successfully validated 1 path(s) by @michaelansel

**Approved paths:**
- `a3f8b912` (Start → Continue → Cave → Victory)

These paths won't be re-checked unless their content changes.
```

## Troubleshooting

### Service won't start

```bash
# Check service status
systemctl --user status continuity-webhook

# Check logs
journalctl --user -u continuity-webhook -n 50

# Verify environment file
cat ~/.config/continuity-webhook/env
```

### Webhook signature verification fails

- Ensure webhook secret matches in GitHub and environment file
- Check nginx/proxy preserves X-Hub-Signature-256 header

### Ollama errors

```bash
# Test ollama API directly
curl -X POST http://localhost:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-oss:20b-fullcontext", "prompt": "Hello", "stream": false}'

# Check if model is available
ollama list

# Test ollama service
curl http://localhost:11434/api/tags
```

### Can't download artifacts

- Verify GitHub token has `repo` scope
- Check token expiration
- Ensure workflow uploaded artifacts with name "allpaths"

## Monitoring

### Service Status

```bash
systemctl --user status continuity-webhook
```

### Status Endpoint (Live Metrics)

```bash
# Check active jobs
curl http://localhost:5000/status | jq '.active_jobs'

# Check metrics
curl http://localhost:5000/status | jq '.metrics'

# View recent jobs
curl http://localhost:5000/status | jq '.recent_completed_jobs'
```

### Recent Logs

```bash
journalctl --user -u continuity-webhook -n 100
```

### Follow Logs

```bash
journalctl --user -u continuity-webhook -f
```

### Restart Service

```bash
systemctl --user restart continuity-webhook
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
2. Restart service: `systemctl --user restart continuity-webhook`
3. Check logs: `journalctl --user -u continuity-webhook -f`
4. Monitor status: `curl http://localhost:5000/status`

## Security Considerations

- Keep `GITHUB_TOKEN` and `WEBHOOK_SECRET` secret
- Environment file has 600 permissions (owner read/write only)
- Service runs as `ubuntu` user (not root)
- Always verify webhook signatures in production
- Validate all artifact contents before processing
- Never execute code from artifacts (text processing only)

## Performance

- Ollama HTTP API averages 20-60 seconds per path (model/complexity dependent)
- Processing happens in background threads (webhook returns 202 immediately)
- Progress updates posted to PR in real-time as each path completes
- Authors can start acting on issues while remaining paths are still being checked
- Service has configurable timeout (default: 120 seconds per path)
- Failed checks don't block PRs (informational comments only)

## Maintenance

### Update Dependencies

```bash
cd services
source venv/bin/activate
pip install --upgrade flask requests gunicorn
systemctl --user restart continuity-webhook  # Restart to use updated packages
```

### Rotate Secrets

1. Generate new webhook secret: `openssl rand -hex 32`
2. Update `~/.config/continuity-webhook/env`
3. Update GitHub webhook settings
4. Restart service: `systemctl --user restart continuity-webhook`

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
