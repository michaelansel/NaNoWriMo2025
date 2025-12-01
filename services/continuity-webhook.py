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

# Import Story Bible validator (Phase 3: World consistency validation)
sys.path.insert(0, str(Path(__file__).parent / "lib"))
from story_bible_validator import (
    validate_against_story_bible,
    merge_validation_results
)

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
processed_workflow_runs = {}  # {workflow_run_id: timestamp} - track processed workflow runs
COMMENT_DEDUP_TTL = 300  # 5 minutes
WORKFLOW_DEDUP_TTL = 600  # 10 minutes (workflows can take longer)

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
    """Verify GitHub webhook signature.

    Implementation notes:
    - WHY: Prevents unauthorized webhook calls that could trigger expensive AI operations
    - Fails closed: rejects webhooks if WEBHOOK_SECRET not configured
    - Uses constant-time comparison to prevent timing attacks
    """
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

    # Compare signatures using constant-time comparison
    # WHY: Prevents timing attacks that could leak the secret
    return hmac.compare_digest(expected_signature, github_signature)


def download_artifact(artifact_url: str, dest_dir: Path) -> bool:
    """Download and extract a GitHub artifact.

    Implementation notes:
    - SECURITY: Validates URL to prevent SSRF attacks
    - SECURITY: Validates ZIP contents to prevent path traversal (Zip Slip)
    - Size limit enforced during extraction (MAX_TEXT_FILE_SIZE)
    """
    token = get_github_token()
    if not token:
        app.logger.error("GitHub token not available, cannot download artifacts")
        return False

    # Validate artifact URL is from GitHub (prevent SSRF)
    # WHY: Prevent attackers from triggering requests to internal services
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
        # SECURITY: Zip Slip vulnerability - malicious ZIPs can contain paths like "../../etc/passwd"
        app.logger.info(f"Extracting artifact to {dest_dir}")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Validate each member to prevent path traversal (Zip Slip)
            for member in zip_ref.namelist():
                # Normalize paths to resolve any .. components
                member_path = os.path.normpath(os.path.join(dest_dir, member))
                dest_dir_normalized = os.path.normpath(dest_dir)

                # Ensure the member path is within dest_dir
                # This blocks paths like "../../../etc/passwd"
                if not member_path.startswith(dest_dir_normalized + os.sep) and member_path != dest_dir_normalized:
                    app.logger.error(f"Attempted path traversal in ZIP: {member}")
                    raise ValueError(f"Invalid path in ZIP archive: {member}")

                # Extract the member (safe after validation)
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
    # - dist/allpaths-metadata/ directory with .txt files (with metadata for AI checking)

    cache_file = artifact_dir / "allpaths-validation-status.json"
    text_dir = artifact_dir / "dist" / "allpaths-metadata"

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

    Implementation notes:
    - WHY: AI could be manipulated to output malicious markdown/HTML
    - DEFENSE IN DEPTH: GitHub already sanitizes, but we add extra layer
    - DoS protection: Limit markdown nesting depth to prevent renderer issues
    """
    if not text:
        return text

    # Remove any javascript: protocol links
    # WHY: javascript:alert(1) in markdown link would execute in some viewers
    text = re.sub(r'javascript:', 'blocked-javascript:', text, flags=re.IGNORECASE)

    # Remove data: protocol links (can be used for XSS)
    # WHY: data:text/html,<script>alert(1)</script> can execute
    text = re.sub(r'data:', 'blocked-data:', text, flags=re.IGNORECASE)

    # Remove file: protocol links
    # WHY: file:///etc/passwd could leak local files
    text = re.sub(r'file:', 'blocked-file:', text, flags=re.IGNORECASE)

    # Escape HTML entities that could be used for injection
    # GitHub markdown should handle this, but defense in depth
    text = text.replace('<script', '&lt;script')
    text = text.replace('</script', '&lt;/script')
    text = text.replace('<iframe', '&lt;iframe')
    text = text.replace('</iframe', '&lt;/iframe')

    # Limit excessive markdown nesting (can cause DoS in some renderers)
    # WHY: Deeply nested markdown like [[[[[...]]]]] can slow/crash renderers
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
    all_checked_paths = results.get('all_checked_paths', [])

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

    # Phase 3: Story Bible validation section
    story_bible_available = any(
        p.get('world_validation') for p in all_checked_paths
    )

    if story_bible_available:
        comment += "### 📖 Story Bible Validation\n\n"
        comment += "✓ Validated against established world constants\n"

        world_issues_count = sum(
            1 for p in all_checked_paths
            if p.get('world_validation', {}).get('has_violations', False)
        )

        if world_issues_count > 0:
            comment += f"⚠️ Found world consistency issues in {world_issues_count} path(s)\n\n"
        else:
            comment += "✅ No world consistency issues detected\n\n"

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

    # Add bulk approval commands section
    if all_checked_paths:
        comment += "\n### 💡 Quick Approval Commands\n\n"
        comment += "Copy-paste these commands to approve multiple paths at once:\n\n"

        # Group paths by severity for bulk approval
        no_issues = [p for p in all_checked_paths if p["severity"] == "none"]
        minor_only = [p for p in all_checked_paths if p["severity"] == "minor"]
        major_only = [p for p in all_checked_paths if p["severity"] == "major"]
        critical_only = [p for p in all_checked_paths if p["severity"] == "critical"]

        # All paths
        all_ids = ' '.join(p["id"] for p in all_checked_paths)
        comment += f"**All paths ({len(all_checked_paths)} total):**\n"
        comment += f"```\n/approve-path {all_ids}\n```\n\n"

        # No issues
        if no_issues:
            no_issue_ids = ' '.join(p["id"] for p in no_issues)
            comment += f"**✅ No issues ({len(no_issues)} paths):**\n"
            comment += f"```\n/approve-path {no_issue_ids}\n```\n\n"

        # Minor issues only
        if minor_only:
            minor_ids = ' '.join(p["id"] for p in minor_only)
            comment += f"**🟢 Minor issues only ({len(minor_only)} paths):**\n"
            comment += f"```\n/approve-path {minor_ids}\n```\n\n"

        # Major issues (with warning)
        if major_only:
            major_ids = ' '.join(p["id"] for p in major_only)
            comment += f"**🟡 Major issues ({len(major_only)} paths - review recommended):**\n"
            comment += f"```\n/approve-path {major_ids}\n```\n\n"

        # Critical issues (with strong warning)
        if critical_only:
            critical_ids = ' '.join(p["id"] for p in critical_only)
            comment += f"**🔴 Critical issues ({len(critical_only)} paths - review required):**\n"
            comment += f"```\n/approve-path {critical_ids}\n```\n\n"

    comment += "\n---\n_Powered by Ollama (gpt-oss:20b-fullcontext)_\n"

    return comment


def format_path_issues(path: dict) -> str:
    """Format issues for a single path, including world validation (Phase 3)."""
    path_id = path.get("id", "unknown")
    route_str = " → ".join(path["route"]) if path["route"] else path_id
    output = f"**Path:** `{path_id}` ({route_str})\n\n"
    output += f"_{sanitize_ai_content(path['summary'])}_\n\n"

    # Path consistency issues
    if path.get("issues"):
        output += "<details>\n<summary>Path Consistency Issues</summary>\n\n"
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

    # Phase 3: World consistency issues
    world_validation = path.get('world_validation')
    if world_validation and world_validation.get('has_violations'):
        output += "<details>\n<summary>World Consistency Issues (Story Bible)</summary>\n\n"
        output += f"_{sanitize_ai_content(world_validation.get('summary', ''))}_\n\n"

        for violation in world_validation.get('violations', []):
            violation_type = violation.get('type', 'unknown')
            severity = violation.get('severity', 'unknown')
            description = sanitize_ai_content(violation.get('description', ''))
            constant_fact = sanitize_ai_content(violation.get('constant_fact', ''))
            passage_statement = sanitize_ai_content(violation.get('passage_statement', ''))

            output += f"- **{violation_type.replace('_', ' ').capitalize()}** ({severity}): {description}\n"
            if constant_fact:
                output += f"  - **Established constant**: \"{constant_fact}\"\n"
            if passage_statement:
                output += f"  - **This passage states**: \"{passage_statement}\"\n"

            evidence = violation.get('evidence', {})
            if evidence and isinstance(evidence, dict):
                const_source = evidence.get('constant_source', '')
                if const_source:
                    output += f"  - **Constant source**: {sanitize_ai_content(const_source)}\n"
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

        # Find the "story-preview" artifact
        story_preview_artifact = None
        for artifact in artifacts_data.get('artifacts', []):
            if artifact['name'] == 'story-preview':
                story_preview_artifact = artifact
                break

        if not story_preview_artifact:
            app.logger.info("[Background] No story-preview artifact found, nothing to check")
            return

        # Download and process artifact
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Download artifact
            artifact_url = story_preview_artifact['archive_download_url']
            if not download_artifact(artifact_url, tmpdir_path):
                app.logger.error("[Background] Failed to download artifact")
                return

            # Check for cancellation (early - before validation starts)
            if cancel_event.is_set():
                app.logger.info(f"[Background] Job cancelled early for PR #{pr_number} (before validation started)")
                post_pr_comment(pr_number, "## 🤖 AI Continuity Check - Cancelled\n\nValidation cancelled before checking began - newer commit or manual request detected.\n\n_This is expected during rapid development. The latest commit will be validated instead._\n\n---\n_Powered by Ollama (gpt-oss:20b-fullcontext)_")
                return

            # Validate structure
            if not validate_artifact_structure(tmpdir_path):
                app.logger.error("[Background] Invalid artifact structure")
                return

            # Get paths to check
            text_dir = tmpdir_path / "dist" / "allpaths-metadata"
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

            # Phase 3: Load Story Bible cache from PR branch for world consistency validation
            story_bible_cache = load_story_bible_cache_from_branch(pr_number)
            story_bible_available = bool(
                story_bible_cache and
                story_bible_cache.get('categorized_facts', {}).get('constants', {})
            )
            if story_bible_available:
                app.logger.info(f"[Story Bible] Story Bible cache loaded, will validate world consistency")
            else:
                app.logger.info(f"[Story Bible] No Story Bible cache available, skipping world validation")

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
                app.logger.info(f"[Background] Job was cancelled during validation (after some paths completed)")
                post_pr_comment(pr_number, "## 🤖 AI Continuity Check - Cancelled\n\nValidation cancelled after checking some paths - newer commit or manual request detected.\n\n_This is expected during rapid development. The latest commit will be validated instead._\n\n---\n_Powered by Ollama (gpt-oss:20b-fullcontext)_")
                return

            # Phase 3: Add Story Bible validation to each checked path
            if story_bible_available:
                app.logger.info(f"[Story Bible] Running world consistency validation for {results['checked_count']} paths")

                # Validate each path against Story Bible constants
                all_paths = results.get('all_checked_paths', [])
                for path_result in all_paths:
                    # Get the path text file
                    path_id = path_result.get('id')
                    text_file = text_dir / f"path-{path_id}.txt"

                    if text_file.exists():
                        try:
                            story_text = text_file.read_text()

                            # Run Story Bible validation
                            world_result = validate_against_story_bible(
                                passage_text=story_text,
                                story_bible_cache=story_bible_cache,
                                passage_id=path_id
                            )

                            # Merge with path consistency results
                            # Note: path_result doesn't have all fields, need to reconstruct
                            path_consistency_result = {
                                'has_issues': path_result.get('has_issues', False),
                                'severity': path_result.get('severity', 'none'),
                                'issues': path_result.get('issues', []),
                                'summary': path_result.get('summary', '')
                            }

                            merged = merge_validation_results(path_consistency_result, world_result)

                            # Update path_result with merged data
                            path_result['world_validation'] = merged.get('world_validation')
                            path_result['severity'] = merged.get('severity')
                            path_result['has_issues'] = merged.get('has_issues')

                        except Exception as e:
                            app.logger.error(f"[Story Bible] Error validating path {path_id}: {e}", exc_info=True)
                            # Continue with other paths

                # Also update paths_with_issues
                paths_with_issues = results.get('paths_with_issues', [])
                for path in paths_with_issues:
                    # Find matching path in all_checked_paths
                    path_id = path.get('id')
                    matching = [p for p in all_paths if p.get('id') == path_id]
                    if matching:
                        # Copy world_validation from merged result
                        path['world_validation'] = matching[0].get('world_validation')
                        path['severity'] = matching[0].get('severity')
                        path['has_issues'] = matching[0].get('has_issues')

                app.logger.info(f"[Story Bible] World consistency validation complete")

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

    # Deduplication: Check if we've already processed this workflow run
    with metrics_lock:
        now = time.time()
        # Clean up old entries
        expired_ids = [wid for wid, ts in processed_workflow_runs.items() if now - ts > WORKFLOW_DEDUP_TTL]
        for wid in expired_ids:
            del processed_workflow_runs[wid]

        # Check if already processed
        if workflow_id in processed_workflow_runs:
            app.logger.info(f"Ignoring duplicate webhook for workflow run {workflow_id}")
            return jsonify({"message": "Duplicate webhook, already processed"}), 200

        # Mark as processed
        processed_workflow_runs[workflow_id] = now

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
    # WHY: New commits supersede old ones, so stop checking outdated code
    # This prevents wasted AI computation and confusing duplicate comments
    with metrics_lock:
        if pr_number in pr_active_jobs:
            old_workflow_id = pr_active_jobs[pr_number]
            if old_workflow_id in active_jobs:
                app.logger.info(f"Cancelling existing job (workflow {old_workflow_id}) for PR #{pr_number}")
                cancel_event = active_jobs[old_workflow_id].get("cancel_event")
                if cancel_event:
                    # Signal cancellation - checked in process_webhook_async loop
                    cancel_event.set()

    # Spawn background thread to process webhook
    # WHY: Return immediately (202 Accepted) so GitHub doesn't timeout
    # Always use 'new-only' mode for automatic workflow triggers (fastest)
    thread = threading.Thread(
        target=process_webhook_async,
        args=(workflow_id, pr_number, artifacts_url, 'new-only'),
        daemon=True  # Dies when main process exits
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
    elif re.search(r'/extract-story-bible\b', comment_body):
        return handle_extract_story_bible_command(payload)
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

    # Check authorization first (before potentially expensive cache operations)
    if not is_authorized(username):
        post_pr_comment(pr_number,
            f"⚠️ @{username} is not authorized to approve paths. Only repository collaborators can approve.")
        return jsonify({"message": "Unauthorized"}), 403

    # Extract path IDs (8-char hex hashes) and category keywords
    path_ids = re.findall(r'\b[a-f0-9]{8}\b', comment_body)

    # Check for category keywords (all, new, modified, unchanged)
    category_keywords = []
    for keyword in ['all', 'new', 'modified', 'unchanged']:
        # Match keyword as whole word (not part of another word)
        if re.search(rf'\b{keyword}\b', comment_body, re.IGNORECASE):
            category_keywords.append(keyword.lower())

    # If no explicit path IDs and no keywords, show error
    if not path_ids and not category_keywords:
        post_pr_comment(pr_number,
            "⚠️ No valid path IDs or categories found.\n\n" +
            "**Format:**\n" +
            "- Specific paths: `/approve-path abc12345 def67890`\n" +
            "- All paths: `/approve-path all`\n" +
            "- By category: `/approve-path new` or `/approve-path modified`")
        return jsonify({"message": "No path IDs"}), 200

    # Process asynchronously (will expand keywords inside the async function)
    thread = threading.Thread(
        target=process_approval_async,
        args=(pr_number, path_ids, username, category_keywords),
        daemon=True
    )
    thread.start()

    return jsonify({"message": "Processing approval", "path_count": len(path_ids), "categories": category_keywords}), 202


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

    # Ignore bot's own comments (which contain helper text with /check-continuity commands)
    bot_markers = [
        '🤖 AI Continuity Check',
        'Powered by Ollama',
        '**Mode:**'
    ]
    if any(marker in comment_body for marker in bot_markers):
        app.logger.info(f"Ignoring bot's own comment")
        return jsonify({"message": "Ignoring bot's own comment"}), 200

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

    # Cancel any existing checks for this PR (manual command supersedes auto-validation)
    # This prevents parallel runs and ensures the user's manual request takes priority
    with metrics_lock:
        if pr_number in pr_active_jobs:
            existing_workflow_id = pr_active_jobs[pr_number]
            if existing_workflow_id in active_jobs:
                app.logger.info(f"Manual command: cancelling existing auto-validation (workflow {existing_workflow_id}) for PR #{pr_number}")
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


def handle_extract_story_bible_command(payload):
    """Handle /extract-story-bible command from PR comments."""
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
            app.logger.info(f"Ignoring duplicate /extract-story-bible for comment {comment_id}")
            return jsonify({"message": "Duplicate webhook"}), 200

        processed_comment_ids[comment_id] = now

    # Ignore bot's own comments
    bot_markers = [
        '📖 Story Bible Extraction',
        'Powered by Ollama',
        '**Mode:**'
    ]
    if any(marker in comment_body for marker in bot_markers):
        app.logger.info(f"Ignoring bot's own comment")
        return jsonify({"message": "Ignoring bot's own comment"}), 200

    # Parse mode from command
    mode = parse_story_bible_command_mode(comment_body)

    app.logger.info(f"Received /extract-story-bible command for PR #{pr_number} with mode={mode} from {username}")

    # Get PR info
    pr_info = get_pr_info(pr_number)
    if not pr_info:
        post_pr_comment(pr_number, "⚠️ Could not retrieve PR information")
        return jsonify({"message": "PR info error"}), 500

    # Find the latest successful workflow run for this PR
    artifacts_url = get_latest_artifacts_url(pr_number)
    if not artifacts_url:
        post_pr_comment(pr_number, "⚠️ No successful workflow run found for this PR. Please ensure the CI has completed successfully at least once.")
        return jsonify({"message": "No artifacts found"}), 404

    # Spawn background thread for processing
    workflow_id = f"story-bible-{pr_number}-{int(time.time())}"

    thread = threading.Thread(
        target=process_story_bible_extraction_async,
        args=(workflow_id, pr_number, artifacts_url, username, mode),
        daemon=True
    )
    thread.start()

    return jsonify({"message": "Extraction started", "mode": mode, "workflow_id": workflow_id}), 202


def parse_story_bible_command_mode(comment_body: str) -> str:
    """Parse extraction mode from /extract-story-bible command.

    Formats:
        /extract-story-bible              -> 'incremental' (default)
        /extract-story-bible full         -> 'full'
        /extract-story-bible incremental  -> 'incremental'
        /extract-story-bible summarize    -> 'summarize'

    Args:
        comment_body: The comment text

    Returns:
        One of: 'incremental', 'full', 'summarize'
    """
    match = re.search(r'/extract-story-bible(?:\s+(full|incremental|summarize))?', comment_body, re.IGNORECASE)

    if match and match.group(1):
        return match.group(1).lower()

    return 'incremental'  # Default


def process_story_bible_extraction_async(workflow_id, pr_number, artifacts_url, username, mode):
    """Process Story Bible extraction in background thread.

    Args:
        workflow_id: Unique ID for this workflow
        pr_number: PR number
        artifacts_url: URL to download artifacts (None for summarize mode)
        username: GitHub username who triggered the command
        mode: One of 'incremental', 'full', or 'summarize'
    """
    # Import the extractor module
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent / 'lib'))
    from story_bible_extractor import (
        extract_facts_from_passage,
        extract_facts_from_passage_with_chunking,
        categorize_all_facts,
        get_passages_to_extract,
        run_summarization,
        calculate_metrics
    )

    try:
        app.logger.info(f"[Story Bible] Processing extraction for PR #{pr_number} with mode={mode}")

        # Post initial comment
        if mode == 'summarize':
            mode_text = 'summarization only (no extraction)'
        elif mode == 'full':
            mode_text = 'full re-extraction'
        else:
            mode_text = 'incremental extraction of new/changed passages'

        post_pr_comment(pr_number, f"""## 📖 Story Bible Extraction - Starting

**Mode:** `{mode}` _({mode_text})_
**Requested by:** @{username}

Downloading artifacts and preparing extraction...

_This may take several minutes. Progress updates will be posted as extraction proceeds._

---
_Powered by Ollama (gpt-oss:20b-fullcontext)_
""")

        # Load cache from PR branch (if exists)
        cache = load_story_bible_cache_from_branch(pr_number)

        # Handle summarize-only mode (skip extraction)
        if mode == 'summarize':
            app.logger.info(f"[Story Bible] Summarize-only mode: skipping extraction")

            # Check that passage_extractions exists
            if not cache:
                post_pr_comment(pr_number, """⚠️ No Story Bible cache found on this branch.

**Next steps:**
- Run `/extract-story-bible` first to extract facts from passages

---
_Powered by Ollama (gpt-oss:20b-fullcontext)_
""")
                return

            if 'passage_extractions' not in cache or not cache['passage_extractions']:
                post_pr_comment(pr_number, """⚠️ No passage extractions found in cache.

**Next steps:**
- Run `/extract-story-bible` first to extract facts from passages

---
_Powered by Ollama (gpt-oss:20b-fullcontext)_
""")
                return

            total_passages = len(cache['passage_extractions'])

            post_pr_comment(pr_number, f"""## 📖 Story Bible Summarization - Processing

Found **{total_passages}** passage(s) with extracted facts.

Running AI summarization to deduplicate and merge facts...
""")

        else:
            # Download artifacts for extraction modes
            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir_path = Path(tmpdir)

                # Download and extract
                if not download_artifact_for_pr(artifacts_url, tmpdir_path):
                    post_pr_comment(pr_number, "⚠️ Failed to download artifacts")
                    return

                # Load allpaths metadata
                metadata_dir = tmpdir_path / "dist" / "allpaths-metadata"

                if not metadata_dir.exists():
                    post_pr_comment(pr_number, "⚠️ No allpaths-metadata found in artifacts. Please ensure the build completed successfully.")
                    return

                # Identify passages to extract
                passages_to_extract = get_passages_to_extract(cache, metadata_dir, mode)

                if not passages_to_extract:
                    post_pr_comment(pr_number, f"""## 📖 Story Bible Extraction - Complete

**Mode:** `{mode}`

No passages need extraction. Story Bible is up to date.

_Use `/extract-story-bible full` to force full re-extraction._

---
_Powered by Ollama (gpt-oss:20b-fullcontext)_
""")
                    return

                # Post list of passages
                total_passages = len(passages_to_extract)
                post_pr_comment(pr_number, f"""## 📖 Story Bible Extraction - Processing

**Mode:** `{mode}`

Found **{total_passages}** passage(s) to extract.

_Progress updates will be posted as each passage completes._
""")

                # Extract facts from each passage
                for idx, (passage_id, passage_file, passage_content) in enumerate(passages_to_extract, 1):
                    app.logger.info(f"[Story Bible] Extracting passage {idx}/{total_passages}: {passage_id}")

                    try:
                        # Call Ollama API with chunking support
                        extracted_facts, chunks_processed = extract_facts_from_passage_with_chunking(
                            passage_id, passage_content
                        )

                        # Update cache
                        if 'passage_extractions' not in cache:
                            cache['passage_extractions'] = {}

                        # Handle new entity-first extraction format
                        # extracted_facts is now a dict with 'entities' and 'facts' keys
                        entities = extracted_facts.get('entities', {})
                        facts_list = extracted_facts.get('facts', [])

                        cache['passage_extractions'][passage_id] = {
                            'content_hash': hashlib.md5(passage_content.encode()).hexdigest(),
                            'extracted_at': datetime.now().isoformat(),
                            'entities': entities,
                            'facts': facts_list,
                            'chunks_processed': chunks_processed,
                            'passage_name': passage_id,
                            'passage_length': len(passage_content)
                        }

                        # Post progress with entity counts
                        char_count = len(entities.get('characters', []))
                        loc_count = len(entities.get('locations', []))
                        item_count = len(entities.get('items', []))

                        # Build entity preview
                        char_names = [c.get('name', 'Unknown') for c in entities.get('characters', [])[:5]]
                        loc_names = [l.get('name', 'Unknown') for l in entities.get('locations', [])[:3]]

                        preview_parts = []
                        if char_names:
                            preview_parts.append(f"**Characters:** {', '.join(char_names)}")
                        if loc_names:
                            preview_parts.append(f"**Locations:** {', '.join(loc_names)}")
                        preview_text = '\n'.join(preview_parts) if preview_parts else "No entities found"

                        post_pr_comment(pr_number, f"""### ✅ Passage {idx}/{total_passages} Complete

**Passage:** `{passage_id}`
**Entities found:** {char_count} characters, {loc_count} locations, {item_count} items

<details>
<summary>Preview entities</summary>

{preview_text}

</details>
""")

                    except Exception as e:
                        app.logger.error(f"[Story Bible] Error extracting passage {passage_id}: {e}", exc_info=True)
                        post_pr_comment(pr_number, f"""### ⚠️ Passage {idx}/{total_passages} Failed

**Passage:** `{passage_id}`
**Error:** Extraction failed

Continuing with remaining passages...
""")
                        continue

        # Stage 2.5: Run AI summarization/deduplication
        app.logger.info(f"[Story Bible] Running AI summarization on {len(cache['passage_extractions'])} passages")
        summarized_facts = None
        summarization_status = "skipped"
        summarization_time = 0.0

        try:
            summarized_facts, summarization_status, summarization_time = run_summarization(
                cache.get('passage_extractions', {})
            )
            app.logger.info(f"[Story Bible] Summarization {summarization_status} in {summarization_time:.2f}s")

            # Store summarization results in cache
            cache['summarized_facts'] = summarized_facts
            cache['summarization_status'] = summarization_status
            cache['summarization_time_seconds'] = summarization_time

        except Exception as e:
            # Graceful degradation: log error but continue with categorization
            app.logger.warning(f"[Story Bible] Summarization failed: {e}, continuing with basic categorization")
            cache['summarization_status'] = 'failed'
            cache['summarization_error'] = str(e)

        # Categorize facts (cross-reference across all passages)
        # Pass summarized_facts if available, otherwise falls back to per-passage extractions
        app.logger.info(f"[Story Bible] Categorizing facts across {len(cache['passage_extractions'])} passages")
        categorized_facts = categorize_all_facts(
            cache.get('passage_extractions', {}),
            summarized_facts=summarized_facts
        )
        cache['categorized_facts'] = categorized_facts

        # Calculate quality metrics
        app.logger.info(f"[Story Bible] Calculating quality metrics")
        extraction_stats = calculate_metrics(cache)
        cache['extraction_stats'] = extraction_stats

        # Update metadata
        total_facts = (
            len(categorized_facts.get('constants', {}).get('world_rules', [])) +
            len(categorized_facts.get('constants', {}).get('setting', [])) +
            len(categorized_facts.get('constants', {}).get('timeline', [])) +
            len(categorized_facts.get('variables', {}).get('events', [])) +
            len(categorized_facts.get('variables', {}).get('outcomes', []))
        )

        cache['meta'] = {
            'last_extracted': datetime.now().isoformat(),
            'total_passages_extracted': len(cache['passage_extractions']),
            'total_facts': total_facts
        }

        # Commit cache to PR branch
        pr_info = get_pr_info(pr_number)
        branch_name = pr_info['head']['ref']

        # Get total_passages for commit message
        if mode == 'summarize':
            total_passages = len(cache['passage_extractions'])
        # else: total_passages already set during extraction

        commit_story_bible_to_branch(pr_number, branch_name, cache, username, mode, total_passages)

        # Post final summary
        character_count = len(categorized_facts.get('characters', {}))
        constant_count = (
            len(categorized_facts.get('constants', {}).get('world_rules', [])) +
            len(categorized_facts.get('constants', {}).get('setting', [])) +
            len(categorized_facts.get('constants', {}).get('timeline', []))
        )
        variable_count = (
            len(categorized_facts.get('variables', {}).get('events', [])) +
            len(categorized_facts.get('variables', {}).get('outcomes', []))
        )

        # Format summarization status for display
        if summarization_status == 'success':
            summarization_display = f"✅ Success ({summarization_time:.1f}s) - facts deduplicated"
        elif summarization_status == 'failed':
            summarization_display = "⚠️ Failed - using per-passage view"
        else:
            summarization_display = "⏭️ Skipped"

        # Customize final comment based on mode
        if mode == 'summarize':
            title = "Story Bible Summarization - Complete"
            passages_label = "Passages processed"
        else:
            title = "Story Bible Extraction - Complete"
            passages_label = "Passages extracted"

        # Format quality metrics for display
        metrics_text = ""
        if extraction_stats:
            character_coverage = extraction_stats.get('character_coverage', 0)
            avg_facts = extraction_stats.get('average_facts_per_passage', 0)
            success_rate = extraction_stats.get('extraction_success_rate', 0) * 100
            dedup_ratio = extraction_stats.get('deduplication_effectiveness', 0) * 100

            metrics_text = f"""
**Quality Metrics:**
- **Character coverage:** {character_coverage} characters detected
- **Extraction success:** {extraction_stats.get('passages_with_facts', 0)}/{extraction_stats.get('total_passages', 0)} passages ({success_rate:.1f}%)
- **Average facts/passage:** {avg_facts:.1f}
- **Deduplication:** {dedup_ratio:.0f}% reduction
"""

        post_pr_comment(pr_number, f"""## 📖 {title}

**Mode:** `{mode}`
**{passages_label}:** {total_passages}
**Total facts:** {total_facts}
**Summarization:** {summarization_display}
{metrics_text}
**Summary:**
- **Constants:** {constant_count} world facts
- **Characters:** {character_count} characters
- **Variables:** {variable_count} player-determined facts

**Story Bible updated:**
- `story-bible-cache.json` committed to branch `{branch_name}`
- Facts cached for incremental updates

**Next steps:**
- Review extracted facts in `story-bible-cache.json`
- Use `/extract-story-bible` again to update as story evolves
- Facts will be preserved and incrementally updated

---
_Powered by Ollama (gpt-oss:20b-fullcontext)_
""")

        app.logger.info(f"[Story Bible] Extraction complete for PR #{pr_number}")

    except Exception as e:
        app.logger.error(f"[Story Bible] Error during extraction: {e}", exc_info=True)
        post_pr_comment(pr_number, "⚠️ Error during extraction. Please contact repository maintainers.")


def load_story_bible_cache_from_branch(pr_number: int) -> Dict:
    """Load story-bible-cache.json from the PR branch if it exists.

    Used for both Story Bible extraction (Phase 2) and validation (Phase 3).

    Args:
        pr_number: Pull request number

    Returns:
        Story Bible cache dict, or empty dict if not found
    """
    pr_info = get_pr_info(pr_number)
    if not pr_info:
        return {}

    branch_name = pr_info['head']['ref']
    token = get_github_token()
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/story-bible-cache.json"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

    try:
        response = requests.get(url, headers=headers, params={"ref": branch_name})
        if response.status_code == 200:
            import base64
            content = response.json()['content']
            decoded = base64.b64decode(content).decode('utf-8')
            cache = json.loads(decoded)
            app.logger.info(f"[Story Bible] Loaded cache from branch {branch_name}")
            return cache
        else:
            app.logger.info(f"[Story Bible] No existing cache found on branch {branch_name}, starting fresh")
            return {}
    except Exception as e:
        app.logger.warning(f"[Story Bible] Could not load cache from branch: {e}")
        return {}


def commit_story_bible_to_branch(pr_number: int, branch_name: str, cache_data: Dict, username: str, mode: str, passages_extracted: int) -> bool:
    """Commit updated Story Bible cache to PR branch."""
    # Serialize cache
    cache_content = json.dumps(cache_data, indent=2, ensure_ascii=False)

    # Build commit message based on mode
    total_facts = cache_data.get('meta', {}).get('total_facts', 0)

    if mode == 'summarize':
        operation = "Re-ran AI summarization"
        detail = f"Processed {passages_extracted} passage(s)"
    elif mode == 'full':
        operation = "Full extraction + summarization"
        detail = f"Extracted facts from {passages_extracted} passage(s)"
    else:  # incremental
        operation = "Incremental extraction + summarization"
        detail = f"Extracted facts from {passages_extracted} passage(s)"

    commit_message = f"""Update Story Bible: {operation}

{detail}
Total facts in cache: {total_facts}

Mode: {mode}
Requested by: @{username}

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
"""

    # Commit to branch
    return commit_file_to_branch(branch_name, 'story-bible-cache.json', cache_content, commit_message)


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


def process_approval_async(pr_number: int, path_ids: List[str], username: str, category_keywords: List[str] = None):
    """Process path approvals in background.

    Args:
        pr_number: Pull request number
        path_ids: Explicit list of path IDs (8-char hex hashes)
        username: User requesting approval
        category_keywords: Optional list of category keywords ('all', 'new', 'modified', 'unchanged')
    """
    try:
        category_keywords = category_keywords or []

        app.logger.info(f"[Approval] Processing paths for PR #{pr_number} by {username} - " +
                       f"explicit IDs: {len(path_ids)}, categories: {category_keywords}")

        # Post initial acknowledgment
        if category_keywords:
            categories_str = ', '.join(f'`{k}`' for k in category_keywords)
            post_pr_comment(pr_number, f"✅ Processing approval for categories: {categories_str}...")
        else:
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

            # Expand category keywords to actual path IDs
            expanded_from_keywords = []
            category_stats = {}

            if category_keywords:
                for keyword in category_keywords:
                    if keyword == 'all':
                        # Get all paths regardless of category
                        for path_id, data in cache.items():
                            if isinstance(data, dict) and path_id not in expanded_from_keywords:
                                expanded_from_keywords.append(path_id)
                        category_stats['all'] = len(expanded_from_keywords)
                    else:
                        # Get paths by specific category
                        count = 0
                        for path_id, data in cache.items():
                            if isinstance(data, dict):
                                if data.get('category') == keyword and path_id not in expanded_from_keywords:
                                    expanded_from_keywords.append(path_id)
                                    count += 1
                        category_stats[keyword] = count

                app.logger.info(f"[Approval] Expanded keywords to {len(expanded_from_keywords)} path IDs: {category_stats}")

            # Combine explicit path IDs with expanded ones (remove duplicates)
            all_path_ids = list(set(path_ids + expanded_from_keywords))

            if not all_path_ids:
                post_pr_comment(pr_number, "⚠️ No paths found to approve. The specified categories may be empty.")
                return

            # Mark paths as validated
            approved_count = 0
            not_found = []
            already_approved = []

            for path_id in all_path_ids:
                if path_id in cache and isinstance(cache[path_id], dict):
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

            # Build commit message
            if category_keywords:
                categories_str = ', '.join(category_keywords)
                commit_message = f"""Mark {approved_count} path(s) as validated ({categories_str})

Categories approved by @{username}: {categories_str}
- Total paths: {len(all_path_ids)}
- Newly approved: {approved_count}
- Already approved: {len(already_approved)}

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
"""
            else:
                commit_message = f"""Mark {approved_count} path(s) as validated

Paths approved by @{username}:
{chr(10).join(f'- {pid}' for pid in all_path_ids if pid not in not_found and pid not in already_approved)}

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
"""

            if not commit_file_to_branch(branch_name, "allpaths-validation-status.json",
                                        cache_content, commit_message):
                post_pr_comment(pr_number, "⚠️ Error: Failed to commit validation cache")
                return

            # Post success comment
            if category_keywords:
                categories_str = ', '.join(f'`{k}`' for k in category_keywords)
                success_lines = [f"✅ Successfully validated {approved_count} path(s) from categories: {categories_str} by @{username}\n"]
                if category_stats:
                    success_lines.append("**Category breakdown:**")
                    for cat, count in category_stats.items():
                        success_lines.append(f"- `{cat}`: {count} path(s)")
                    success_lines.append("")
            else:
                success_lines = [f"✅ Successfully validated {approved_count} path(s) by @{username}\n"]

            if approved_count > 0 and not category_keywords:
                success_lines.append("**Approved paths:**")
                for pid in all_path_ids:
                    if pid not in not_found and pid not in already_approved:
                        route = cache.get(pid, {}).get("route", pid)
                        success_lines.append(f"- `{pid}` ({route})")

            if already_approved:
                success_lines.append(f"\n**Already approved:** {len(already_approved)} path(s)")
                if len(already_approved) <= 10:
                    success_lines.append(', '.join(f'`{p}`' for p in already_approved))

            if not_found:
                success_lines.append(f"\n**Not found:** {len(not_found)} path(s)")
                if len(not_found) <= 10:
                    success_lines.append(', '.join(f'`{p}`' for p in not_found))

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
    """Download story-preview artifact for approval processing."""
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

        # Find the story-preview artifact
        for artifact in artifacts_data.get('artifacts', []):
            if artifact['name'] == 'story-preview':
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
