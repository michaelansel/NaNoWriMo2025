#!/usr/bin/env python3
"""
GitHub webhook service for AI-based story continuity checking.

This service:
1. Receives GitHub workflow_run webhooks
2. Downloads artifacts from completed PR builds
3. Runs AI continuity checking
4. Posts results back to the PR

Security:
- Verifies GitHub webhook signatures (HMAC-SHA256)
- Only processes text files (no code execution)
- Validates artifact structure before processing
"""

import os
import sys
import json
import hmac
import hashlib
import tempfile
import shutil
import zipfile
import subprocess
import threading
import re
import jwt
import time
from pathlib import Path
from typing import Dict, List
from flask import Flask, request, jsonify
import requests

# Import the checker module dynamically (filename has hyphens, not underscores)
import importlib.util
_checker_script_path = Path(__file__).parent.parent / "scripts" / "check-story-continuity.py"
_spec = importlib.util.spec_from_file_location("check_story_continuity", _checker_script_path)
_checker_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_checker_module)
check_paths_with_progress = _checker_module.check_paths_with_progress
get_unvalidated_paths = _checker_module.get_unvalidated_paths
load_validation_cache = _checker_module.load_validation_cache
save_validation_cache = _checker_module.save_validation_cache

# Configuration (from environment variables)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
REPO_OWNER = os.getenv("REPO_OWNER", "michaelansel")
REPO_NAME = os.getenv("REPO_NAME", "NaNoWriMo2025")
PORT = int(os.getenv("WEBHOOK_PORT", "5000"))
MAX_TEXT_FILE_SIZE = 1024 * 1024  # 1MB limit for artifact text files

# GitHub App configuration (optional - falls back to PAT if not set)
GITHUB_APP_ID = os.getenv("GITHUB_APP_ID")
GITHUB_APP_PRIVATE_KEY_PATH = os.getenv("GITHUB_APP_PRIVATE_KEY_PATH")
GITHUB_APP_INSTALLATION_ID = os.getenv("GITHUB_APP_INSTALLATION_ID")

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
CHECKER_SCRIPT = PROJECT_ROOT / "scripts" / "check-story-continuity.py"

# Flask app
app = Flask(__name__)

# Global state for tracking active jobs and metrics
from datetime import datetime
from collections import defaultdict
import time

active_jobs = {}  # {workflow_id: {pr_number, start_time, current_path, total_paths, status, cancel_event}}
pr_active_jobs = {}  # {pr_number: workflow_id} - track which workflow is active for each PR
job_history = []  # Recent completed jobs
metrics = defaultdict(int)  # Various counters
metrics_lock = threading.Lock()

# Webhook deduplication (GitHub can send webhooks multiple times)
processed_comment_ids = {}  # {comment_id: timestamp} - track processed comments
COMMENT_DEDUP_TTL = 300  # 5 minutes

# GitHub App authentication - token cache
_token_cache = {
    'token': None,
    'expires_at': 0
}


def generate_jwt(app_id: str, private_key: str) -> str:
    """Generate JWT for GitHub App authentication."""
    now = int(time.time())
    payload = {
        'iat': now - 60,  # Issued at (60s in past for clock drift)
        'exp': now + (10 * 60),  # Expires in 10 minutes
        'iss': app_id  # Issuer (GitHub App ID)
    }
    return jwt.encode(payload, private_key, algorithm='RS256')


def get_installation_token(app_id: str, private_key: str, installation_id: str) -> str:
    """Get installation access token for GitHub App."""
    jwt_token = generate_jwt(app_id, private_key)

    headers = {
        'Authorization': f'Bearer {jwt_token}',
        'Accept': 'application/vnd.github+json'
    }

    url = f'https://api.github.com/app/installations/{installation_id}/access_tokens'
    response = requests.post(url, headers=headers)
    response.raise_for_status()

    return response.json()['token']


def get_github_token() -> str:
    """Get GitHub token - either from GitHub App or PAT fallback."""
    # Check if using GitHub App
    if GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY_PATH and GITHUB_APP_INSTALLATION_ID:
        # Check if cached token is still valid
        now = time.time()
        if _token_cache['token'] and now < _token_cache['expires_at']:
            return _token_cache['token']

        try:
            # Load private key
            with open(GITHUB_APP_PRIVATE_KEY_PATH, 'r') as f:
                private_key = f.read()

            # Generate new installation token
            token = get_installation_token(GITHUB_APP_ID, private_key, GITHUB_APP_INSTALLATION_ID)

            # Cache token (expires in 1 hour, refresh 5 minutes early)
            _token_cache['token'] = token
            _token_cache['expires_at'] = now + (55 * 60)

            app.logger.info("Using GitHub App authentication")
            return token
        except Exception as e:
            app.logger.error(f"Error getting GitHub App token, falling back to PAT: {e}")
            # Fall through to PAT fallback

    # Fall back to PAT
    if GITHUB_TOKEN:
        app.logger.info("Using PAT authentication")
    return GITHUB_TOKEN


def verify_signature(payload_body: bytes, signature_header: str) -> bool:
    """Verify GitHub webhook signature."""
    if not WEBHOOK_SECRET:
        app.logger.error("WEBHOOK_SECRET not set, rejecting webhook for security")
        return False  # Fail closed - require secret to be configured

    if not signature_header:
        app.logger.error("No signature header provided")
        return False

    # GitHub sends signature as "sha256=<hmac>"
    hash_algorithm, github_signature = signature_header.split('=', 1)

    if hash_algorithm != 'sha256':
        app.logger.error(f"Unsupported hash algorithm: {hash_algorithm}")
        return False

    # Compute expected signature
    mac = hmac.new(
        WEBHOOK_SECRET.encode(),
        msg=payload_body,
        digestmod=hashlib.sha256
    )
    expected_signature = mac.hexdigest()

    # Compare signatures (constant time comparison)
    return hmac.compare_digest(expected_signature, github_signature)


def download_artifact(artifact_url: str, dest_dir: Path) -> bool:
    """Download and extract a GitHub artifact."""
    token = get_github_token()
    if not token:
        app.logger.error("GitHub token not available, cannot download artifacts")
        return False

    # Validate artifact URL is from GitHub (prevent SSRF)
    from urllib.parse import urlparse
    parsed_url = urlparse(artifact_url)
    allowed_hosts = ['api.github.com', 'github.com', 'objects.githubusercontent.com', 'pipelines.actions.githubusercontent.com']
    if parsed_url.netloc not in allowed_hosts:
        app.logger.error(f"Artifact URL has invalid domain: {parsed_url.netloc}")
        return False

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

    try:
        # Download artifact (returns a ZIP file)
        app.logger.info(f"Downloading artifact from {artifact_url}")
        response = requests.get(artifact_url, headers=headers, stream=True, timeout=60)
        response.raise_for_status()

        # Save to temporary zip file
        zip_path = dest_dir / "artifact.zip"
        with open(zip_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        # Extract zip file with path traversal protection
        app.logger.info(f"Extracting artifact to {dest_dir}")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Validate each member to prevent path traversal (Zip Slip)
            for member in zip_ref.namelist():
                member_path = os.path.normpath(os.path.join(dest_dir, member))
                dest_dir_normalized = os.path.normpath(dest_dir)

                # Ensure the member path is within dest_dir
                if not member_path.startswith(dest_dir_normalized + os.sep) and member_path != dest_dir_normalized:
                    app.logger.error(f"Attempted path traversal in ZIP: {member}")
                    raise ValueError(f"Invalid path in ZIP archive: {member}")

                # Extract the member
                zip_ref.extract(member, dest_dir)

        # Remove zip file
        zip_path.unlink()

        return True

    except Exception as e:
        app.logger.error(f"Error downloading artifact: {e}")
        return False


def validate_artifact_structure(artifact_dir: Path) -> bool:
    """Validate that artifact contains expected files and structure."""
    # Expected structure:
    # - allpaths-validation-status.json (at root)
    # - dist/allpaths-text/ directory with .txt files

    cache_file = artifact_dir / "allpaths-validation-status.json"
    text_dir = artifact_dir / "dist" / "allpaths-text"

    if not cache_file.exists():
        app.logger.error(f"Missing validation cache file: {cache_file}")
        return False

    if not text_dir.exists() or not text_dir.is_dir():
        app.logger.error(f"Missing or invalid text directory: {text_dir}")
        return False

    # Check that text files exist and are reasonable size (< 1MB each)
    txt_files = list(text_dir.glob("*.txt"))
    if not txt_files:
        app.logger.info("No text files found (empty paths, this is OK)")
        return True  # Empty is valid

    for txt_file in txt_files:
        if txt_file.stat().st_size > MAX_TEXT_FILE_SIZE:
            app.logger.error(f"Text file too large: {txt_file}")
            return False

    return True


def translate_passage_ids(text: str, id_to_name: Dict[str, str]) -> str:
    """Replace passage IDs with real passage names in text."""
    if not id_to_name:
        return text

    for passage_id, passage_name in id_to_name.items():
        # Replace IDs with names, adding quotes for clarity
        text = text.replace(passage_id, f'"{passage_name}"')

    return text


def sanitize_ai_content(text: str) -> str:
    """
    Sanitize AI-generated content before including in PR comments.

    Protects against markdown injection, XSS, and malicious links.
    """
    if not text:
        return text

    # Remove any javascript: protocol links
    text = re.sub(r'javascript:', 'blocked-javascript:', text, flags=re.IGNORECASE)

    # Remove data: protocol links (can be used for XSS)
    text = re.sub(r'data:', 'blocked-data:', text, flags=re.IGNORECASE)

    # Remove file: protocol links
    text = re.sub(r'file:', 'blocked-file:', text, flags=re.IGNORECASE)

    # Escape HTML entities that could be used for injection
    # GitHub markdown should handle this, but defense in depth
    text = text.replace('<script', '&lt;script')
    text = text.replace('</script', '&lt;/script')
    text = text.replace('<iframe', '&lt;iframe')
    text = text.replace('</iframe', '&lt;/iframe')

    # Limit excessive markdown nesting (can cause DoS in some renderers)
    if text.count('[') > 50 or text.count('![') > 20:
        app.logger.warning("AI content has suspicious number of markdown links, truncating")
        text = text[:1000] + "\n\n[Content truncated for safety]"

    return text


def run_continuity_check(text_dir: Path, cache_file: Path, pr_number: int = None, progress_callback=None, cancel_event=None, mode='new-only') -> dict:
    """Run the AI continuity checking script with optional progress callbacks."""
    try:
        app.logger.info(f"Running continuity checker on {text_dir} with mode={mode}")

        # Call the checker function directly with progress callback, cancel event, and mode
        results = check_paths_with_progress(text_dir, cache_file, progress_callback, cancel_event, mode)

        return results

    except Exception as e:
        # Log detailed error to server logs only
        app.logger.error(f"Error running continuity checker: {e}", exc_info=True)
        # Return generic error to user
        return {
            "checked_count": 0,
            "paths_with_issues": [],
            "summary": "Error: Internal error during continuity check. Please contact repository maintainers."
        }


def format_pr_comment(results: dict) -> str:
    """Format the continuity check results as a PR comment."""
    mode = results.get('mode', 'new-only')
    stats = results.get('statistics', {})

    # Mode explanation
    mode_explanations = {
        'new-only': 'checked only new paths',
        'modified': 'checked new and modified paths',
        'all': 'checked all paths (full validation)'
    }
    mode_text = mode_explanations.get(mode, mode)

    if results["checked_count"] == 0:
        return f"""## 🤖 AI Continuity Check

**Mode:** `{mode}` _({mode_text})_

{results["summary"]}

_No paths to check with this mode._
"""

    # Build comment header with mode and statistics
    comment = f"""## 🤖 AI Continuity Check

**Mode:** `{mode}` _({mode_text})_

**Summary:** {results["summary"]}

"""

    # Add statistics if available
    if stats:
        comment += "### Validation Scope\n"
        comment += f"- ✓ **Checked:** {stats['checked']} path(s)\n"
        comment += f"- ⊘ **Skipped:** {stats['skipped']} path(s)\n"
        comment += f"  - {stats['new']} new, {stats['modified']} modified, {stats['unchanged']} unchanged\n\n"

        # Suggest broader checking if paths were skipped
        if mode == 'new-only' and (stats['modified'] > 0 or stats['unchanged'] > 0):
            comment += "_Use `/check-continuity modified` or `/check-continuity all` for broader checking._\n\n"
        elif mode == 'modified' and stats['unchanged'] > 0:
            comment += "_Use `/check-continuity all` for full validation._\n\n"

    if not results["paths_with_issues"]:
        comment += "### ✅ All Paths Passed\n\n"
        comment += f"No issues found in {results['checked_count']} path(s).\n"
    else:
        comment += f"### ⚠️ Issues Found\n\n"
        comment += f"Found issues in **{len(results['paths_with_issues'])}** of {results['checked_count']} path(s).\n\n"

        # Group by severity
        critical = [p for p in results["paths_with_issues"] if p["severity"] == "critical"]
        major = [p for p in results["paths_with_issues"] if p["severity"] == "major"]
        minor = [p for p in results["paths_with_issues"] if p["severity"] == "minor"]

        if critical:
            comment += f"#### 🔴 Critical Issues ({len(critical)})\n\n"
            for path in critical:
                comment += format_path_issues(path)

        if major:
            comment += f"#### 🟡 Major Issues ({len(major)})\n\n"
            for path in major:
                comment += format_path_issues(path)

        if minor:
            comment += f"#### 🟢 Minor Issues ({len(minor)})\n\n"
            for path in minor:
                comment += format_path_issues(path)

    comment += "\n---\n_Powered by Ollama (gpt-oss:20b-fullcontext)_\n"

    return comment


def format_path_issues(path: dict) -> str:
    """Format issues for a single path."""
    path_id = path.get("id", "unknown")
    route_str = " → ".join(path["route"]) if path["route"] else path_id
    output = f"**Path:** `{path_id}` ({route_str})\n\n"
    output += f"_{sanitize_ai_content(path['summary'])}_\n\n"

    if path.get("issues"):
        output += "<details>\n<summary>Details</summary>\n\n"
        for issue in path["issues"]:
            issue_type = issue.get("type", "unknown")
            severity = issue.get("severity", "unknown")
            description = sanitize_ai_content(issue.get("description", "No description"))
            location = sanitize_ai_content(issue.get("location", ""))

            output += f"- **{issue_type.capitalize()}** ({severity}): {description}"
            if location:
                output += f" _{location}_"
            output += "\n"

            # Add context with quotes if available
            context = issue.get("context", {})
            if context and isinstance(context, dict):
                quotes = context.get("quotes", [])
                explanation = sanitize_ai_content(context.get("explanation", ""))

                if quotes or explanation:
                    output += "\n  **In context:**\n"
                    if explanation:
                        output += f"  {explanation}\n"
                    if quotes:
                        output += "\n"
                        for quote in quotes:
                            passage_name = quote.get("passage", "unknown")
                            quote_text = sanitize_ai_content(quote.get("text", ""))
                            if quote_text:
                                output += f'  > In "{passage_name}": "{quote_text}"\n'
                    output += "\n"

        output += "</details>\n\n"

    return output


def post_pr_comment(pr_number: int, comment: str) -> bool:
    """Post a comment to a GitHub PR."""
    token = get_github_token()
    if not token:
        app.logger.error("GitHub token not available, cannot post comment")
        return False

    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues/{pr_number}/comments"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }
    data = {"body": comment}

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        app.logger.info(f"Posted comment to PR #{pr_number}")
        return True
    except Exception as e:
        app.logger.error(f"Error posting PR comment: {e}")
        return False


def get_pr_number_from_workflow(workflow_run_id: int) -> int:
    """Get PR number associated with a workflow run."""
    token = get_github_token()
    if not token:
        return None

    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/actions/runs/{workflow_run_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

        # Get PR number from pull_requests array
        pull_requests = data.get("pull_requests", [])
        if pull_requests:
            return pull_requests[0]["number"]

        return None
    except Exception as e:
        app.logger.error(f"Error getting PR number: {e}")
        return None


def process_webhook_async(workflow_id, pr_number, artifacts_url, mode='new-only'):
    """Process webhook in background thread.

    Args:
        workflow_id: Unique identifier for this validation job
        pr_number: Pull request number
        artifacts_url: URL to fetch workflow artifacts
        mode: Validation mode ('new-only', 'modified', 'all')
    """
    cancel_event = threading.Event()

    try:
        app.logger.info(f"[Background] Processing workflow {workflow_id} for PR #{pr_number} with mode={mode}")

        # Track this job
        with metrics_lock:
            active_jobs[workflow_id] = {
                "pr_number": pr_number,
                "start_time": datetime.now(),
                "current_path": 0,
                "total_paths": 0,
                "status": "initializing",
                "cancel_event": cancel_event
            }
            pr_active_jobs[pr_number] = workflow_id  # Mark this workflow as active for this PR
            metrics["total_webhooks_received"] += 1

        # Fetch artifact list
        token = get_github_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json"
        }

        response = requests.get(artifacts_url, headers=headers)
        response.raise_for_status()
        artifacts_data = response.json()

        # Find the "allpaths" artifact
        allpaths_artifact = None
        for artifact in artifacts_data.get('artifacts', []):
            if artifact['name'] == 'allpaths':
                allpaths_artifact = artifact
                break

        if not allpaths_artifact:
            app.logger.info("[Background] No allpaths artifact found, nothing to check")
            return

        # Download and process artifact
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Download artifact
            artifact_url = allpaths_artifact['archive_download_url']
            if not download_artifact(artifact_url, tmpdir_path):
                app.logger.error("[Background] Failed to download artifact")
                return

            # Check for cancellation
            if cancel_event.is_set():
                app.logger.info(f"[Background] Job cancelled for PR #{pr_number}, stopping")
                post_pr_comment(pr_number, "## 🤖 AI Continuity Check - Cancelled\n\nValidation cancelled - newer commit detected.\n\n---\n_Powered by Ollama (gpt-oss:20b-fullcontext)_")
                return

            # Validate structure
            if not validate_artifact_structure(tmpdir_path):
                app.logger.error("[Background] Invalid artifact structure")
                return

            # Get paths to check
            text_dir = tmpdir_path / "dist" / "allpaths-text"
            cache_file = tmpdir_path / "allpaths-validation-status.json"
            mapping_file = tmpdir_path / "dist" / "allpaths-passage-mapping.json"

            # Load passage ID mapping for translating results
            id_to_name = {}
            if mapping_file.exists():
                try:
                    with open(mapping_file, 'r') as f:
                        mapping_data = json.load(f)
                        id_to_name = mapping_data.get('id_to_name', {})
                        app.logger.info(f"Loaded passage ID mapping with {len(id_to_name)} passages")
                except Exception as e:
                    app.logger.warning(f"Could not load passage mapping: {e}")

            # Load cache to see what paths need checking
            cache = load_validation_cache(cache_file)
            unvalidated, stats = get_unvalidated_paths(cache, text_dir, mode)

            if not unvalidated:
                app.logger.info(f"[Background] No paths to check with mode '{mode}'")
                comment = f"""## 🤖 AI Continuity Check

**Mode:** `{mode}`

No paths to check with this mode.

**Path Statistics:**
- New: {stats['new']}
- Modified: {stats['modified']}
- Unchanged: {stats['unchanged']}

_Use `/check-continuity modified` or `/check-continuity all` to check other paths._

---
_Powered by Ollama (gpt-oss:20b-fullcontext)_
"""
                post_pr_comment(pr_number, comment)
                return

            # Post initial comment with list of paths
            total_paths = len(unvalidated)

            # Update job status with total paths
            with metrics_lock:
                active_jobs[workflow_id]["total_paths"] = total_paths
                active_jobs[workflow_id]["status"] = "checking_paths"

            # Build path list with routes from cache
            path_list_items = []
            for path_id, text_file in unvalidated:
                # Try to get route from cache
                route = cache.get(path_id, {}).get("route", "")
                if route:
                    path_list_items.append(f"- `{path_id}` ({route})")
                else:
                    path_list_items.append(f"- `{path_id}`")
            path_list = "\n".join(path_list_items)

            # Mode explanation
            mode_explanations = {
                'new-only': 'checking only new paths',
                'modified': 'checking new and modified paths',
                'all': 'checking all paths (full validation)'
            }
            mode_text = mode_explanations.get(mode, mode)

            # Build suggestions for other modes
            other_modes_text = ""
            if mode == 'new-only' and (stats['modified'] > 0 or stats['unchanged'] > 0):
                other_modes_text = f"\n_**Note:** Skipped {stats['modified']} modified and {stats['unchanged']} unchanged paths. Use `/check-continuity modified` or `/check-continuity all` for broader checking._\n"
            elif mode == 'modified' and stats['unchanged'] > 0:
                other_modes_text = f"\n_**Note:** Skipped {stats['unchanged']} unchanged paths. Use `/check-continuity all` for full validation._\n"

            initial_comment = f"""## 🤖 AI Continuity Check - Starting

**Mode:** `{mode}` _({mode_text})_

Found **{total_paths}** path(s) to check.

**Path Statistics:**
- New: {stats['new']}
- Modified: {stats['modified']}
- Unchanged: {stats['unchanged']}
- **Checking:** {stats['checked']}
- **Skipping:** {stats['skipped']}
{other_modes_text}
**Paths to validate:**
{path_list}

_This may take up to 5 minutes per passage. Updates will be posted as each path completes._

💡 **Commands:**
- Approve paths: `/approve-path abc12345 def67890`
- Check with different scope: `/check-continuity modified` or `/check-continuity all`

---
_Powered by Ollama (gpt-oss:20b-fullcontext)_
"""
            app.logger.info(f"[Background] Posting initial comment for {total_paths} paths")
            post_pr_comment(pr_number, initial_comment)

            # Define progress callback
            def progress_callback(current, total, path_result):
                """Post progress update and update job status."""
                # Update job status
                with metrics_lock:
                    if workflow_id in active_jobs:
                        active_jobs[workflow_id]["current_path"] = current
                        metrics["total_paths_checked"] += 1

                try:
                    path_id = path_result.get("id", "unknown")
                    # Get actual route from cache (has passage names, not hex IDs)
                    route_str = cache.get(path_id, {}).get("route", path_id)
                    severity = path_result.get("severity", "none")
                    summary = sanitize_ai_content(translate_passage_ids(path_result.get("summary", ""), id_to_name))
                    issues = path_result.get("issues", [])

                    # Choose emoji based on severity
                    emoji = "✅"
                    if severity == "critical":
                        emoji = "🔴"
                    elif severity == "major":
                        emoji = "🟡"
                    elif severity == "minor":
                        emoji = "🟢"

                    update_comment = f"""### {emoji} Path {current}/{total} Complete

**Path:** `{path_id}` ({route_str})
**Result:** {severity}
**Summary:** {summary}
"""

                    # Add detailed issues if present
                    if issues:
                        update_comment += "\n<details>\n<summary>Details</summary>\n\n"
                        for issue in issues:
                            issue_type = issue.get("type", "unknown")
                            issue_severity = issue.get("severity", "unknown")
                            description = sanitize_ai_content(translate_passage_ids(issue.get("description", "No description"), id_to_name))
                            location = sanitize_ai_content(translate_passage_ids(issue.get("location", ""), id_to_name))

                            update_comment += f"- **{issue_type.capitalize()}** ({issue_severity}): {description}"
                            if location:
                                update_comment += f" _{location}_"
                            update_comment += "\n"

                            # Add context with quotes if available
                            context = issue.get("context", {})
                            if context and isinstance(context, dict):
                                quotes = context.get("quotes", [])
                                explanation = sanitize_ai_content(context.get("explanation", ""))

                                if quotes or explanation:
                                    update_comment += "\n  **In context:**\n"
                                    if explanation:
                                        update_comment += f"  {explanation}\n"
                                    if quotes:
                                        update_comment += "\n"
                                        for quote in quotes:
                                            passage_id = quote.get("passage", "")
                                            quote_text = sanitize_ai_content(quote.get("text", ""))
                                            # Translate passage ID to name
                                            passage_name = id_to_name.get(passage_id, passage_id) if passage_id else "unknown"
                                            if quote_text:
                                                update_comment += f'  > In "{passage_name}": "{quote_text}"\n'
                                    update_comment += "\n"

                        update_comment += "</details>\n"

                    # Add approval helper text
                    update_comment += f"\n💡 **To approve this path:** reply `/approve-path {path_id}`\n"

                    app.logger.info(f"[Background] Posting progress update: {current}/{total}")
                    post_pr_comment(pr_number, update_comment)
                except Exception as e:
                    app.logger.error(f"[Background] Error in progress callback: {e}", exc_info=True)

            # Run continuity check with progress callback, cancel event, and mode
            results = run_continuity_check(text_dir, cache_file, pr_number, progress_callback, cancel_event, mode)

            # Check if job was cancelled during validation
            if cancel_event.is_set():
                app.logger.info(f"[Background] Job was cancelled during validation")
                post_pr_comment(pr_number, "## 🤖 AI Continuity Check - Cancelled\n\nValidation cancelled - newer commit detected.\n\n---\n_Powered by Ollama (gpt-oss:20b-fullcontext)_")
                return

            # Translate passage IDs in final results
            if results.get("paths_with_issues"):
                for path in results["paths_with_issues"]:
                    # Replace hex ID route with actual passage names from cache
                    path_id = path.get("id")
                    if path_id and path_id in cache:
                        # Get the route with actual passage names from the cache
                        cache_route = cache[path_id].get("route", "")
                        if cache_route:
                            # Convert route string to list format expected by format_path_issues
                            path["route"] = cache_route.split(" → ")

                    if id_to_name:
                        path["summary"] = translate_passage_ids(path["summary"], id_to_name)
                        if path.get("issues"):
                            for issue in path["issues"]:
                                issue["description"] = translate_passage_ids(issue["description"], id_to_name)
                                if issue.get("location"):
                                    issue["location"] = translate_passage_ids(issue["location"], id_to_name)
                                # Translate passage IDs in context quotes
                                context = issue.get("context", {})
                                if context and isinstance(context, dict):
                                    if context.get("explanation"):
                                        context["explanation"] = translate_passage_ids(context["explanation"], id_to_name)
                                    quotes = context.get("quotes", [])
                                    for quote in quotes:
                                        if quote.get("passage"):
                                            # Translate passage ID to passage name
                                            passage_id = quote["passage"]
                                            quote["passage"] = id_to_name.get(passage_id, passage_id)
                                        if quote.get("text"):
                                            quote["text"] = translate_passage_ids(quote["text"], id_to_name)

            # Format and post final summary comment
            comment = format_pr_comment(results)
            if not post_pr_comment(pr_number, comment):
                app.logger.error("[Background] Failed to post final comment")
                return

            app.logger.info(f"[Background] Successfully posted continuity check results to PR #{pr_number}")

            # Mark job as complete
            with metrics_lock:
                if workflow_id in active_jobs:
                    job_info = active_jobs.pop(workflow_id)
                    job_info["status"] = "completed"
                    job_info["end_time"] = datetime.now()
                    job_info["duration_seconds"] = (job_info["end_time"] - job_info["start_time"]).total_seconds()
                    job_history.append(job_info)
                    # Keep only last 50 jobs in history
                    if len(job_history) > 50:
                        job_history.pop(0)
                    metrics["total_jobs_completed"] += 1

                # Clean up PR tracking if this is still the active job for this PR
                if pr_active_jobs.get(pr_number) == workflow_id:
                    pr_active_jobs.pop(pr_number, None)

    except Exception as e:
        app.logger.error(f"[Background] Error processing webhook: {e}", exc_info=True)

        # Mark job as failed
        with metrics_lock:
            if workflow_id in active_jobs:
                job_info = active_jobs.pop(workflow_id)
                job_info["status"] = "failed" if "Job cancelled" not in str(e) else "cancelled"
                job_info["error"] = str(e)
                job_info["end_time"] = datetime.now()
                job_info["duration_seconds"] = (job_info["end_time"] - job_info["start_time"]).total_seconds()
                job_history.append(job_info)
                if len(job_history) > 50:
                    job_history.pop(0)
                if "Job cancelled" not in str(e):
                    metrics["total_jobs_failed"] += 1

            # Clean up PR tracking if this is still the active job for this PR
            if pr_active_jobs.get(pr_number) == workflow_id:
                pr_active_jobs.pop(pr_number, None)


@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle GitHub webhooks."""
    # Verify signature
    signature = request.headers.get('X-Hub-Signature-256')
    if not verify_signature(request.data, signature):
        app.logger.error("Invalid webhook signature")
        return jsonify({"error": "Invalid signature"}), 401

    # Parse event
    event_type = request.headers.get('X-GitHub-Event')
    payload = request.json

    app.logger.info(f"Received {event_type} event")

    # Route to appropriate handler
    if event_type == 'issue_comment':
        return handle_comment_webhook(payload)
    elif event_type == 'workflow_run':
        return handle_workflow_webhook(payload)
    else:
        return jsonify({"message": "Event ignored"}), 200


def handle_workflow_webhook(payload):
    """Handle workflow_run webhooks for AI continuity checking."""
    # Only handle completed workflows
    if payload.get('action') != 'completed':
        return jsonify({"message": "Workflow not completed, ignoring"}), 200

    # Only handle workflows on pull requests
    workflow_run = payload.get('workflow_run', {})
    if workflow_run.get('event') != 'pull_request':
        return jsonify({"message": "Not a PR workflow, ignoring"}), 200

    # Only handle successful workflows
    if workflow_run.get('conclusion') != 'success':
        app.logger.info(f"Workflow failed with conclusion: {workflow_run.get('conclusion')}")
        return jsonify({"message": "Workflow not successful, ignoring"}), 200

    # Get PR number
    workflow_id = workflow_run.get('id')
    pr_number = get_pr_number_from_workflow(workflow_id)

    if not pr_number:
        app.logger.error("Could not determine PR number")
        return jsonify({"error": "Could not determine PR number"}), 400

    app.logger.info(f"Processing workflow {workflow_id} for PR #{pr_number}")

    # Get artifacts URL
    artifacts_url = workflow_run.get('artifacts_url')
    if not artifacts_url:
        app.logger.error("No artifacts URL in workflow")
        return jsonify({"error": "No artifacts URL"}), 400

    # Cancel any existing job for this PR
    with metrics_lock:
        if pr_number in pr_active_jobs:
            old_workflow_id = pr_active_jobs[pr_number]
            if old_workflow_id in active_jobs:
                app.logger.info(f"Cancelling existing job (workflow {old_workflow_id}) for PR #{pr_number}")
                cancel_event = active_jobs[old_workflow_id].get("cancel_event")
                if cancel_event:
                    cancel_event.set()  # Signal cancellation

    # Spawn background thread to process webhook
    # Always use 'new-only' mode for automatic workflow triggers
    thread = threading.Thread(
        target=process_webhook_async,
        args=(workflow_id, pr_number, artifacts_url, 'new-only'),
        daemon=True
    )
    thread.start()

    # Return immediately
    app.logger.info(f"Accepted webhook for PR #{pr_number}, processing in background with mode=new-only")
    return jsonify({"message": "Webhook accepted, processing in background", "pr": pr_number}), 202


def handle_comment_webhook(payload):
    """Handle issue_comment webhooks for commands."""
    action = payload.get('action')
    if action != 'created':
        return jsonify({"message": "Not a new comment"}), 200

    # Check if it's a PR (not an issue)
    if 'pull_request' not in payload.get('issue', {}):
        return jsonify({"message": "Not a PR comment"}), 200

    comment_body = payload['comment']['body']

    # Route to appropriate handler
    if re.search(r'/check-continuity\b', comment_body):
        return handle_check_continuity_command(payload)
    elif re.search(r'/approve-path\b', comment_body):
        return handle_approve_path_command(payload)
    else:
        return jsonify({"message": "No recognized command"}), 200


def handle_approve_path_command(payload):
    """Handle /approve-path command from PR comments."""
    comment_body = payload['comment']['body']
    pr_number = payload['issue']['number']
    username = payload['comment']['user']['login']
    comment_id = payload['comment']['id']

    # Deduplication: Check if we've already processed this comment
    with metrics_lock:
        now = time.time()
        # Clean up old entries
        expired_ids = [cid for cid, ts in processed_comment_ids.items() if now - ts > COMMENT_DEDUP_TTL]
        for cid in expired_ids:
            del processed_comment_ids[cid]

        # Check if already processed
        if comment_id in processed_comment_ids:
            app.logger.info(f"Ignoring duplicate webhook for comment {comment_id}")
            return jsonify({"message": "Duplicate webhook, already processed"}), 200

        # Mark as processed
        processed_comment_ids[comment_id] = now

    # Ignore bot's own progress comments by checking for multiple bot markers
    # This prevents self-triggering from the helper text in progress comments
    bot_markers = [
        '💡 **To approve this path:**',
        '🤖 AI Continuity Check',
        'Path {current}/{total} Complete'  # Not using f-string, just checking pattern
    ]
    if any(marker in comment_body for marker in bot_markers):
        return jsonify({"message": "Ignoring bot's own comment"}), 200

    # Extract path IDs (8-char hex hashes)
    path_ids = re.findall(r'\b[a-f0-9]{8}\b', comment_body)

    if not path_ids:
        post_pr_comment(pr_number,
            "⚠️ No valid path IDs found. Format: `/approve-path abc12345 def67890`")
        return jsonify({"message": "No path IDs"}), 200

    # Check authorization
    if not is_authorized(username):
        post_pr_comment(pr_number,
            f"⚠️ @{username} is not authorized to approve paths. Only repository collaborators can approve.")
        return jsonify({"message": "Unauthorized"}), 403

    # Process asynchronously
    thread = threading.Thread(
        target=process_approval_async,
        args=(pr_number, path_ids, username),
        daemon=True
    )
    thread.start()

    return jsonify({"message": "Processing approval", "path_count": len(path_ids)}), 202


def handle_check_continuity_command(payload):
    """Handle /check-continuity command from PR comments."""
    comment_body = payload['comment']['body']
    pr_number = payload['issue']['number']
    username = payload['comment']['user']['login']
    comment_id = payload['comment']['id']

    # Deduplication check
    with metrics_lock:
        now = time.time()
        expired_ids = [cid for cid, ts in processed_comment_ids.items() if now - ts > COMMENT_DEDUP_TTL]
        for cid in expired_ids:
            del processed_comment_ids[cid]

        if comment_id in processed_comment_ids:
            app.logger.info(f"Ignoring duplicate /check-continuity for comment {comment_id}")
            return jsonify({"message": "Duplicate webhook"}), 200

        processed_comment_ids[comment_id] = now

    # Parse mode from command
    mode = parse_check_command_mode(comment_body)

    app.logger.info(f"Received /check-continuity command for PR #{pr_number} with mode={mode} from {username}")

    # Get PR info to find the latest commit
    pr_info = get_pr_info(pr_number)
    if not pr_info:
        post_pr_comment(pr_number, "⚠️ Could not retrieve PR information")
        return jsonify({"message": "PR info error"}), 500

    commit_sha = pr_info['head']['sha']

    # Find the latest successful workflow run for this PR
    token = get_github_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

    # Get workflow runs for this PR
    workflows_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/actions/runs?event=pull_request&per_page=20"
    try:
        response = requests.get(workflows_url, headers=headers)
        response.raise_for_status()
        runs_data = response.json()

        # Find the most recent successful run for this PR
        artifacts_url = None
        for run in runs_data.get('workflow_runs', []):
            # Check if this run is for our PR and completed successfully
            if (run.get('conclusion') == 'success' and
                run.get('event') == 'pull_request' and
                run.get('pull_requests')):

                # Check if this run is for our PR number
                pr_list = run.get('pull_requests', [])
                if any(pr.get('number') == pr_number for pr in pr_list):
                    artifacts_url = run['artifacts_url']
                    app.logger.info(f"Found artifacts for PR #{pr_number} at workflow run {run['id']}")
                    break

        if not artifacts_url:
            post_pr_comment(pr_number, "⚠️ No successful workflow run found for this PR. Please ensure the CI has completed successfully at least once.")
            return jsonify({"message": "No artifacts found"}), 404

    except Exception as e:
        app.logger.error(f"Error fetching workflow runs: {e}")
        post_pr_comment(pr_number, "⚠️ Error fetching workflow information")
        return jsonify({"message": "API error"}), 500

    # Cancel any existing checks for this PR
    with metrics_lock:
        if pr_number in pr_active_jobs:
            existing_workflow_id = pr_active_jobs[pr_number]
            if existing_workflow_id in active_jobs:
                app.logger.info(f"Cancelling existing job {existing_workflow_id} for PR #{pr_number}")
                active_jobs[existing_workflow_id]['cancel_event'].set()

    # Spawn background thread for processing using the existing process_webhook_async
    workflow_id = f"manual-{pr_number}-{int(time.time())}"

    thread = threading.Thread(
        target=process_webhook_async,
        args=(workflow_id, pr_number, artifacts_url, mode),
        daemon=True
    )
    thread.start()

    return jsonify({"message": "Check started", "mode": mode, "workflow_id": workflow_id}), 202


def is_authorized(username: str) -> bool:
    """Check if user is a repo collaborator."""
    token = get_github_token()
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/collaborators/{username}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

    try:
        response = requests.get(url, headers=headers)
        return response.status_code == 204  # 204 = is collaborator
    except Exception as e:
        app.logger.error(f"Error checking authorization: {e}")
        return False


def parse_check_command_mode(comment_body: str) -> str:
    """Parse validation mode from /check-continuity command.

    Supported formats:
        /check-continuity           -> 'new-only' (default)
        /check-continuity new-only  -> 'new-only'
        /check-continuity modified  -> 'modified'
        /check-continuity all       -> 'all'

    Args:
        comment_body: The comment text

    Returns:
        One of: 'new-only', 'modified', 'all'
    """
    # Match /check-continuity optionally followed by a mode
    match = re.search(r'/check-continuity(?:\s+(new-only|modified|all))?', comment_body, re.IGNORECASE)

    if not match:
        return 'new-only'  # Default if command not found

    mode = match.group(1)
    if mode:
        return mode.lower()

    return 'new-only'  # Default if no mode specified


def process_approval_async(pr_number: int, path_ids: List[str], username: str):
    """Process path approvals in background."""
    try:
        app.logger.info(f"[Approval] Processing {len(path_ids)} paths for PR #{pr_number} by {username}")

        # Post initial acknowledgment
        post_pr_comment(pr_number, f"✅ Processing approval for {len(path_ids)} path(s)...")

        # Get PR info to find branch name
        pr_info = get_pr_info(pr_number)
        if not pr_info:
            post_pr_comment(pr_number, "⚠️ Error: Could not retrieve PR information")
            return

        branch_name = pr_info['head']['ref']
        repo_full_name = pr_info['head']['repo']['full_name']

        # Validate branch name format (alphanumeric, dash, underscore, slash, dot)
        if not re.match(r'^[a-zA-Z0-9/_.-]+$', branch_name):
            post_pr_comment(pr_number, "⚠️ Error: Invalid branch name format")
            app.logger.error(f"Invalid branch name: {branch_name}")
            return

        # Download the latest artifact from the most recent workflow run on this PR
        artifacts_url = get_latest_artifacts_url(pr_number)
        if not artifacts_url:
            post_pr_comment(pr_number, "⚠️ Error: No workflow artifacts found for this PR")
            return

        # Download and extract artifact
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            if not download_artifact_for_pr(artifacts_url, tmpdir_path):
                post_pr_comment(pr_number, "⚠️ Error: Failed to download validation cache")
                return

            cache_file = tmpdir_path / "allpaths-validation-status.json"
            if not cache_file.exists():
                post_pr_comment(pr_number, "⚠️ Error: Validation cache not found in artifacts")
                return

            # Load cache
            cache = load_validation_cache(cache_file)

            # Mark paths as validated
            approved_count = 0
            not_found = []
            already_approved = []

            for path_id in path_ids:
                if path_id in cache:
                    if cache[path_id].get("validated", False):
                        already_approved.append(path_id)
                    else:
                        cache[path_id]["validated"] = True
                        cache[path_id]["validated_at"] = datetime.now().isoformat()
                        cache[path_id]["validated_by"] = username
                        approved_count += 1
                else:
                    not_found.append(path_id)

            # Save updated cache
            save_validation_cache(cache_file, cache)

            # Commit cache back to PR branch
            cache_content = cache_file.read_text()
            commit_message = f"""Mark {approved_count} path(s) as validated

Paths approved by @{username}:
{chr(10).join(f'- {pid}' for pid in path_ids if pid not in not_found and pid not in already_approved)}

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
"""

            if not commit_file_to_branch(branch_name, "allpaths-validation-status.json",
                                        cache_content, commit_message):
                post_pr_comment(pr_number, "⚠️ Error: Failed to commit validation cache")
                return

            # Post success comment
            success_lines = [f"✅ Successfully validated {approved_count} path(s) by @{username}\n"]

            if approved_count > 0:
                success_lines.append("**Approved paths:**")
                for pid in path_ids:
                    if pid not in not_found and pid not in already_approved:
                        route = cache.get(pid, {}).get("route", pid)
                        success_lines.append(f"- `{pid}` ({route})")

            if already_approved:
                success_lines.append(f"\n**Already approved:** {', '.join(f'`{p}`' for p in already_approved)}")

            if not_found:
                success_lines.append(f"\n**Not found:** {', '.join(f'`{p}`' for p in not_found)}")

            success_lines.append("\nThese paths won't be re-checked unless their content changes.")

            post_pr_comment(pr_number, '\n'.join(success_lines))

            app.logger.info(f"[Approval] Successfully approved {approved_count} paths for PR #{pr_number}")

    except Exception as e:
        # Log detailed error to server only
        app.logger.error(f"[Approval] Error: {e}", exc_info=True)
        # Return generic error to user
        post_pr_comment(pr_number, "⚠️ Error processing approval. Please contact repository maintainers.")


def get_pr_info(pr_number: int) -> Dict:
    """Get PR information from GitHub API."""
    token = get_github_token()
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/pulls/{pr_number}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        app.logger.error(f"Error getting PR info: {e}")
        return None


def get_latest_artifacts_url(pr_number: int) -> str:
    """Get artifacts URL from most recent successful workflow run for this PR."""
    token = get_github_token()
    # Get workflow runs for this PR
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/actions/runs"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

    try:
        # Get recent workflow runs
        response = requests.get(url, headers=headers, params={"per_page": 50})
        response.raise_for_status()
        runs = response.json().get("workflow_runs", [])

        # Find the most recent successful run for this PR
        for run in runs:
            pull_requests = run.get("pull_requests", [])
            if any(pr["number"] == pr_number for pr in pull_requests):
                if run["conclusion"] == "success":
                    return run["artifacts_url"]

        return None
    except Exception as e:
        app.logger.error(f"Error getting artifacts URL: {e}")
        return None


def download_artifact_for_pr(artifacts_url: str, dest_dir: Path) -> bool:
    """Download allpaths artifact for approval processing."""
    token = get_github_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

    try:
        # Get artifact list
        response = requests.get(artifacts_url, headers=headers)
        response.raise_for_status()
        artifacts_data = response.json()

        # Find the allpaths artifact
        for artifact in artifacts_data.get('artifacts', []):
            if artifact['name'] == 'allpaths':
                return download_artifact(artifact['archive_download_url'], dest_dir)

        return False
    except Exception as e:
        app.logger.error(f"Error downloading artifact: {e}")
        return False


def commit_file_to_branch(branch_name: str, file_path: str, content: str, message: str) -> bool:
    """Commit a file to a branch using GitHub API."""
    token = get_github_token()
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{file_path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

    try:
        # Get current file SHA (required for updates)
        response = requests.get(url, headers=headers, params={"ref": branch_name})
        current_sha = None
        if response.status_code == 200:
            current_sha = response.json()["sha"]

        # Commit the file
        import base64
        encoded_content = base64.b64encode(content.encode()).decode()

        data = {
            "message": message,
            "content": encoded_content,
            "branch": branch_name
        }
        if current_sha:
            data["sha"] = current_sha

        response = requests.put(url, headers=headers, json=data)
        response.raise_for_status()

        app.logger.info(f"Successfully committed {file_path} to {branch_name}")
        return True
    except requests.HTTPError as e:
        # Log detailed error to server only, don't expose to users
        app.logger.error(f"Error committing file: {e}")
        if e.response:
            app.logger.error(f"Response status: {e.response.status_code}")
            app.logger.error(f"Response body: {e.response.text[:500]}")  # Limit length
        return False
    except Exception as e:
        app.logger.error(f"Error committing file: {e}")
        return False


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    # Determine authentication mode
    github_app_configured = bool(GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY_PATH and GITHUB_APP_INSTALLATION_ID)
    auth_mode = "github_app" if github_app_configured else "pat"

    status = {
        "status": "ok",
        "authentication_mode": auth_mode,
        "github_app_configured": github_app_configured,
        "github_token_set": bool(GITHUB_TOKEN),
        "webhook_secret_set": bool(WEBHOOK_SECRET),
        "checker_script_exists": CHECKER_SCRIPT.exists()
    }
    return jsonify(status), 200


@app.route('/status', methods=['GET'])
def status():
    """Status and metrics endpoint showing active jobs and statistics."""
    with metrics_lock:
        # Format active jobs
        active_jobs_list = []
        for workflow_id, job_info in active_jobs.items():
            active_jobs_list.append({
                "workflow_id": workflow_id,
                "pr_number": job_info["pr_number"],
                "start_time": job_info["start_time"].isoformat(),
                "duration_seconds": (datetime.now() - job_info["start_time"]).total_seconds(),
                "current_path": job_info.get("current_path", 0),
                "total_paths": job_info.get("total_paths", 0),
                "status": job_info.get("status", "processing")
            })

        # Format recent job history (last 10)
        recent_jobs = job_history[-10:]

        # Calculate uptime
        if hasattr(status, '_start_time'):
            uptime_seconds = (datetime.now() - status._start_time).total_seconds()
        else:
            status._start_time = datetime.now()
            uptime_seconds = 0

        response = {
            "active_jobs": active_jobs_list,
            "active_job_count": len(active_jobs_list),
            "recent_completed_jobs": recent_jobs,
            "metrics": dict(metrics),
            "uptime_seconds": uptime_seconds
        }

    return jsonify(response), 200


def main():
    """Main entry point."""
    # Validate configuration
    if not GITHUB_TOKEN:
        print("WARNING: GITHUB_TOKEN not set", file=sys.stderr)
        print("Set GITHUB_TOKEN environment variable to enable artifact download and PR commenting", file=sys.stderr)

    if not WEBHOOK_SECRET:
        print("WARNING: WEBHOOK_SECRET not set", file=sys.stderr)
        print("Webhook signature verification will be skipped (development only!)", file=sys.stderr)

    if not CHECKER_SCRIPT.exists():
        print(f"ERROR: Checker script not found at {CHECKER_SCRIPT}", file=sys.stderr)
        sys.exit(1)

    print(f"Starting webhook service on port {PORT}...")
    print(f"Repository: {REPO_OWNER}/{REPO_NAME}")
    print(f"Checker script: {CHECKER_SCRIPT}")

    # Run Flask app
    app.run(host='0.0.0.0', port=PORT, debug=False)


if __name__ == '__main__':
    main()
