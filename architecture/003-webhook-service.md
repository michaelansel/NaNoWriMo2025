# ADR-003: GitHub Webhook Service for AI Validation

## Status

Accepted

## Context

After implementing the AllPaths format and validation cache, we had a manual workflow:
1. Push code to PR
2. Wait for GitHub Actions to build
3. Download artifacts manually
4. Run AI validation script locally
5. Review results
6. Manually update validation cache
7. Commit cache back to PR

This manual process was:
- **Time-consuming**: 5-10 minutes of manual work per PR
- **Error-prone**: Easy to forget steps or make mistakes
- **Inconsistent**: Not all PRs got validated
- **Blocking**: Had to wait for validation before review
- **Non-collaborative**: Results not visible to reviewers

We needed an automated way to:
1. Trigger AI validation when PR builds complete
2. Post results back to the PR automatically
3. Allow developers to approve paths via PR comments
4. Support different validation modes (new-only, modified, all)
5. Provide real-time progress updates

## Decision

We decided to implement a **self-hosted GitHub webhook service** that:

1. **Receives webhooks** from GitHub when workflows complete
2. **Downloads artifacts** from successful PR builds
3. **Runs AI validation** using local Ollama instance
4. **Posts results to PRs** as comments with real-time progress
5. **Supports PR commands** for approval and re-validation
6. **Runs asynchronously** with background processing
7. **Provides monitoring** via health and status endpoints

**Architecture**:
- **Framework**: Flask (Python web framework)
- **Runtime**: Gunicorn WSGI server
- **Reverse Proxy**: Nginx with Let's Encrypt SSL
- **Service**: Systemd user service (not root)
- **AI Engine**: Local Ollama (gpt-oss:20b-fullcontext)

**Security**:
- HMAC-SHA256 webhook signature verification
- GitHub App authentication (with PAT fallback)
- Artifact validation (structure, size, paths)
- Content sanitization (prevent XSS in AI output)
- Authorization checks (only collaborators can approve)

## Consequences

### Positive

1. **Fully Automated**: Zero manual steps for basic validation
2. **Fast Feedback**: Results posted within minutes of PR push
3. **Visible**: All team members see validation results
4. **Interactive**: Commands allow re-validation and approval
5. **Progressive**: Real-time updates as each path completes
6. **Self-Hosted**: No API costs, data stays private
7. **Flexible**: Multiple validation modes supported
8. **Auditable**: All actions tracked in PR comments

### Negative

1. **Infrastructure**: Requires self-hosted server
2. **Maintenance**: Service needs monitoring and updates
3. **Complexity**: More moving parts (Flask, Ollama, systemd)
4. **Single Point of Failure**: If service down, no auto-validation
5. **Local Processing**: Limited by server hardware
6. **Setup Overhead**: Initial configuration takes time

### Trade-offs

**Self-Hosted vs. Cloud Service**:
- **Chose self-hosted** for data privacy and zero API costs
- **Trade-off**: More maintenance burden

**Real-Time Updates vs. Single Summary**:
- **Chose real-time** for better UX (developers can act sooner)
- **Trade-off**: More PR comment noise

**GitHub App vs. PAT**:
- **Chose both** with App as primary, PAT as fallback
- **Trade-off**: More complex authentication flow

## Alternatives Considered

### 1. GitHub Actions Only

**Approach**: Run AI validation in GitHub Actions workflow

**Rejected because**:
- Actions runners lack GPU for fast inference
- Would need to install Ollama on each run (slow)
- API-based AI services cost money
- Validation would block deployment
- Can't post incremental updates easily

### 2. Cloud Function (AWS Lambda, Google Cloud Functions)

**Approach**: Serverless webhook receiver

**Rejected because**:
- Still need Ollama somewhere (Lambda doesn't support large models)
- Cold start latency
- Execution time limits (Lambda 15 min max)
- More complex deployment
- Costs scale with usage

### 3. GitHub App with Webhook Forwarding

**Approach**: GitHub App that forwards to local service

**Rejected because**:
- Adds extra hop (latency)
- More complex architecture
- Still need local service anyway
- Doesn't solve core problems

### 4. Poll-Based System

**Approach**: Cron job checks for new PRs and validates

**Rejected because**:
- Delayed feedback (polling interval)
- More complex (need to track processed PRs)
- Wastes resources (polling when idle)
- No real-time updates

### 5. Manual Workflow with GitHub CLI

**Approach**: Script using `gh` CLI to download and comment

**Rejected because**:
- Still manual (defeats purpose)
- Doesn't integrate with PR lifecycle
- No real-time feedback
- Requires local execution

## Implementation Details

### Webhook Flow

```
GitHub sends workflow_run webhook
    ↓
Nginx receives HTTPS request
    ↓
Forward to Flask (localhost:5000)
    ↓
Verify HMAC signature
    ↓
Check event type and conclusion
    ↓
Return 202 Accepted (immediately)
    ↓
Spawn background thread
    ↓
Download artifacts from GitHub
    ↓
Extract and validate artifact
    ↓
Load validation cache
    ↓
Post initial comment (list of paths)
    ↓
For each path to validate:
      Call Ollama API
      Parse AI response
      Post progress comment
    ↓
Post final summary comment
    ↓
Update job metrics
```

### Security Layers

**Layer 1: Webhook Signature**
- Verify HMAC-SHA256 signature
- Reject invalid signatures immediately
- Prevent webhook spoofing

**Layer 2: Artifact Validation**
- Validate artifact URL is from GitHub
- Check artifact structure before processing
- Limit file sizes (1MB per text file)
- Prevent path traversal in ZIP extraction

**Layer 3: Content Sanitization**
- Remove javascript: protocol links
- Escape HTML injection attempts
- Limit markdown nesting depth
- Truncate suspicious content

**Layer 4: Authorization**
- Check collaborator status for approvals
- Verify user permissions before actions
- Log unauthorized attempts

### Background Processing

**Why Asynchronous**:
- Webhook timeout: GitHub waits max 30 seconds
- AI validation: Can take 5-30 minutes
- Solution: Return 202 Accepted immediately, process in background

**Implementation**:
```python
thread = threading.Thread(
    target=process_webhook_async,
    args=(workflow_id, pr_number, artifacts_url, mode),
    daemon=True
)
thread.start()
return jsonify({"message": "Accepted"}), 202
```

**Job Tracking**:
- Active jobs stored in memory
- Status endpoint shows progress
- Cancellation support (newer commits supersede)

### PR Commands

**Implemented Commands**:

1. `/check-continuity [mode]`
   - Trigger validation with specific mode
   - Modes: new-only, modified, all
   - Default: new-only

2. `/approve-path <id1> <id2> ...`
   - Approve specific paths by ID
   - Commits updated cache to PR branch
   - Only collaborators authorized

3. `/approve-path all`
   - Approve all checked paths
   - Useful after reviewing bulk results

4. `/approve-path new`
   - Approve all new paths
   - Category-based bulk approval

**Command Processing**:
1. Receive issue_comment webhook
2. Parse command from comment body
3. Verify authorization
4. Process in background thread
5. Post confirmation comment
6. Commit results to PR branch

### GitHub App Authentication

**Primary: GitHub App**
- Generate JWT from app credentials
- Exchange for installation token
- Token valid 1 hour
- Cache and refresh automatically

**Fallback: Personal Access Token**
- Used if GitHub App not configured
- Simpler setup for personal repos
- No automatic refresh

**Implementation**:
```python
def get_github_token() -> str:
    if GITHUB_APP_ID:
        return get_installation_token(...)
    else:
        return GITHUB_TOKEN  # PAT fallback
```

### Monitoring and Observability

**Health Endpoint** (`/health`):
```json
{
  "status": "ok",
  "authentication_mode": "github_app",
  "github_token_set": true,
  "webhook_secret_set": true,
  "checker_script_exists": true
}
```

**Status Endpoint** (`/status`):
```json
{
  "active_jobs": [...],
  "active_job_count": 2,
  "recent_completed_jobs": [...],
  "metrics": {
    "total_webhooks_received": 42,
    "total_paths_checked": 187,
    "total_jobs_completed": 35
  },
  "uptime_seconds": 86400
}
```

**Logging**:
- systemd journal: `journalctl --user -u continuity-webhook`
- Structured logging with log levels
- Request/response logging
- Error tracking with stack traces

## Deployment

### Service Setup

**Installation** (`services/setup.sh`):
1. Create config directory
2. Generate webhook secret
3. Prompt for GitHub token
4. Create environment file
5. Install Python dependencies
6. Install systemd service
7. Enable auto-start

**Systemd Service**:
```ini
[Unit]
Description=Story Continuity Webhook Service
After=network.target

[Service]
Type=simple
ExecStart=/path/to/venv/bin/gunicorn ...
EnvironmentFile=/path/to/env
Restart=always

[Install]
WantedBy=default.target
```

**HTTPS Setup**:
- Nginx reverse proxy
- Let's Encrypt certificate
- Auto-renewal via certbot

### GitHub Configuration

**Webhook Settings**:
- Payload URL: `https://your-server.com/webhook`
- Content type: `application/json`
- Secret: From setup.sh
- Events: Workflow runs, Issue comments
- Active: Yes

**Workflow Integration**:
```yaml
- name: Upload allpaths artifacts
  if: github.event_name == 'pull_request'
  uses: actions/upload-artifact@v4
  with:
    name: story-preview
    path: |
      dist/
      allpaths-validation-status.json
```

## Success Criteria

The webhook service is successful if:

1. ✅ Validates PRs automatically within 15 minutes
2. ✅ Posts results to PR with 100% reliability
3. ✅ Supports all validation modes
4. ✅ Allows path approval via commands
5. ✅ Provides real-time progress updates
6. ✅ Runs securely (no vulnerabilities)
7. ✅ Maintains 99%+ uptime
8. ✅ Handles multiple concurrent PRs

## Observed Benefits

**Developer Experience**:
- No manual validation steps
- Results visible in PR within minutes
- Can approve paths without leaving GitHub
- Real-time feedback during validation

**Team Collaboration**:
- All members see validation results
- Reviewers can see AI feedback
- Approval history tracked in git

**Time Savings**:
- Manual workflow: 5-10 min per PR
- Automated: 0 manual time
- **Improvement**: 100% reduction in manual effort

## Future Enhancements

Potential improvements:

1. **Parallel Processing**: Validate multiple paths concurrently
2. **Job Queue**: Handle multiple PRs with priority
3. **Persistent State**: Redis for job tracking (survive restarts)
4. **Web Dashboard**: UI for monitoring and history
5. **Metrics Export**: Prometheus metrics for monitoring
6. **Retry Logic**: Automatic retry on transient failures
7. **Rate Limiting**: Protect against abuse

## Scaling Considerations

**Current Limitations**:
- Single-threaded validation per PR
- In-memory job state (lost on restart)
- One Ollama instance (single server)

**If Scaling Needed**:
1. **Worker Pool**: Parallel path validation
2. **Multiple Servers**: Load-balanced webhook receivers
3. **Distributed Ollama**: Multiple inference nodes
4. **Job Queue**: Redis/RabbitMQ for coordination
5. **Shared Storage**: S3 for artifacts and cache

## Maintenance

**Regular Tasks**:
- Monitor logs weekly
- Check disk usage monthly
- Update dependencies quarterly
- Rotate secrets annually

**Incident Response**:
1. Check `/health` endpoint
2. Review recent logs
3. Restart service if needed
4. Test with manual webhook
5. Document incident

**Backup Strategy**:
- Environment config backed up
- Service config in git
- No critical data on server (cache in git)

## Security Considerations

**Attack Vectors**:
- Webhook spoofing: Mitigated by HMAC verification
- Artifact tampering: Validated structure and size
- XSS injection: AI output sanitized
- Unauthorized approval: Collaborator check
- SSRF: Artifact URL validation

**Best Practices**:
- Run as non-root user
- Minimal permissions
- Environment variables for secrets
- Regular security updates
- Audit logs

## References

- Webhook Service: `/services/continuity-webhook.py`
- Service README: `/services/README.md`
- Setup Script: `/services/setup.sh`
- AI Checker: `/scripts/check-story-continuity.py`

## Related ADRs

- ADR-001: AllPaths Format for AI Continuity Validation
- ADR-002: Validation Cache Architecture
- ADR-004: Content-Based Hashing for Change Detection
