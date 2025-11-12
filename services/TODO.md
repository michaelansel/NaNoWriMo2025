# Pending Improvements for AI Continuity Checking Service

## Current Status (as of implementation)

### ✅ Completed:
- Webhook service receives GitHub events (HTTPS via nginx + Let's Encrypt)
- Background async processing (returns 202 immediately)
- AI checker script uses ollama HTTP API (~24s per path, clean JSON)
- Progress callback support in checker script
- User systemd service configured

### 🚧 In Progress:
- Need to update webhook service to use progress callbacks
- Need to add initial "checking started" PR comment
- Need to post progress updates as paths complete

### ❌ Not Yet Implemented:

#### 1. **Webhook Service: Progress Updates to PR**
**File:** `services/continuity-webhook.py`
**Location:** `process_webhook_async()` function

**Changes Needed:**
```python
# After downloading artifacts, post initial comment:
initial_comment = f"""## 🤖 AI Continuity Check - Starting

Found {total_paths} new story path(s) to check.

**Paths to validate:**
{list_of_paths}

_This may take 5-10 minutes. Updates will be posted as each path completes._
"""
post_pr_comment(pr_number, initial_comment)

# Define progress callback:
def progress_callback(current, total, path_result):
    update_comment = f"""### Path {current}/{total} Complete

**Route:** {path_result['route']}
**Result:** {path_result['severity']} - {path_result['summary']}
"""
    post_pr_comment(pr_number, update_comment)

# Call checker with callback:
from scripts.check_story_continuity import check_paths_with_progress
result = check_paths_with_progress(text_dir, cache_file, progress_callback)
```

#### 2. **Webhook Service: Status/Metrics Endpoint**
**File:** `services/continuity-webhook.py`

**Add new endpoint:**
```python
# Track active jobs in module-level dict
active_jobs = {}  # pr_number -> {status, current, total, started_at}

@app.route('/status', methods=['GET'])
def status():
    return jsonify({
        "active_jobs": len(active_jobs),
        "jobs": active_jobs
    })

@app.route('/status/<int:pr_number>', methods=['GET'])
def pr_status(pr_number):
    job = active_jobs.get(pr_number)
    if not job:
        return jsonify({"error": "No active job for this PR"}), 404
    return jsonify(job)
```

#### 3. **Better Logging in Background Threads**
**Issue:** Background thread logs don't appear in journald

**Solution:** Use Python's logging module with custom handler:
```python
import logging
import systemd.journal

# Configure logging to journald
logger = logging.getLogger('continuity-webhook')
logger.addHandler(systemd.journal.JournalHandler())
logger.setLevel(logging.INFO)

# Replace all app.logger calls in background with:
logger.info("[Background] message")
```

#### 4. **Increase or Make Timeout Configurable**
**File:** `services/continuity-webhook.py`

**Current:** 600s (10 min) hardcoded timeout in `run_continuity_check()`

**Change to:**
```python
CHECKER_TIMEOUT = int(os.getenv("CHECKER_TIMEOUT", "1200"))  # 20 min default
```

#### 5. **Error Handling and Retry Logic**
**Files:** Both `continuity-webhook.py` and `check-story-continuity.py`

**Add:**
- Retry failed ollama calls (up to 3 times with exponential backoff)
- Better error messages in PR comments
- Fallback if ollama is unavailable

#### 6. **Update Documentation**
**Files to update:**
- `services/README.md` - Add ollama API info, progress updates
- `services/DEPLOYMENT.md` - Update with final implementation details
- `services/setup-https.md` - Add actual nginx config used

**Key changes from initial design:**
- Using ollama HTTP API instead of CLI subprocess
- Progress updates via PR comments (not single final comment)
- User systemd service (not system service)
- Timeout increased to handle all paths

#### 7. **Testing Improvements**
**Add test script:** `services/test-checker.sh`
```bash
#!/bin/bash
# Quick test of checker without full webhook flow
cd /tmp
mkdir -p test-run
# Download artifacts from latest PR
# Run checker locally
# Verify output format
```

#### 8. **Performance Optimization**
**Possible improvements:**
- Cache ollama model in memory (first request is slowest)
- Parallel checking of multiple paths (requires careful resource management)
- Incremental PR comment updates (edit single comment instead of posting many)

## Implementation Priority

**High Priority (blocking merge):**
1. Progress updates to PR (points 1)
2. Better logging (point 3)

**Medium Priority (post-merge improvements):**
3. Status endpoint (point 2)
4. Configurable timeout (point 4)
5. Documentation updates (point 6)

**Low Priority (nice to have):**
6. Error handling/retry (point 5)
7. Test improvements (point 7)
8. Performance optimization (point 8)

## Test Plan

Once progress updates are implemented:

1. **Manual Test:**
   - Push commit to PR branch
   - Watch for initial "checking started" comment
   - Verify progress updates appear
   - Check final summary is accurate

2. **Load Test:**
   - Create PR with many path changes
   - Verify system handles 20+ paths
   - Check memory usage stays reasonable

3. **Error Test:**
   - Stop ollama service
   - Trigger webhook
   - Verify graceful error message posted

## Notes

- Ollama HTTP API endpoint: `http://localhost:11434/api/generate`
- Each path takes ~20-30 seconds with gpt-oss:20b-fullcontext
- Background threads need explicit logging configuration
- PR comments have rate limits (check GitHub API docs)
