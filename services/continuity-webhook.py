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

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
CHECKER_SCRIPT = PROJECT_ROOT / "scripts" / "check-story-continuity.py"

# Flask app
app = Flask(__name__)

# Global state for tracking active jobs and metrics
from datetime import datetime
from collections import defaultdict
import time

active_jobs = {}  # {workflow_id: {pr_number, start_time, current_path, total_paths, status}}
job_history = []  # Recent completed jobs
metrics = defaultdict(int)  # Various counters
metrics_lock = threading.Lock()


def verify_signature(payload_body: bytes, signature_header: str) -> bool:
    """Verify GitHub webhook signature."""
    if not WEBHOOK_SECRET:
        app.logger.warning("WEBHOOK_SECRET not set, skipping signature verification")
        return True  # Allow in development, but log warning

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
    if not GITHUB_TOKEN:
        app.logger.error("GITHUB_TOKEN not set, cannot download artifacts")
        return False

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    try:
        # Download artifact (returns a ZIP file)
        app.logger.info(f"Downloading artifact from {artifact_url}")
        response = requests.get(artifact_url, headers=headers, stream=True)
        response.raise_for_status()

        # Save to temporary zip file
        zip_path = dest_dir / "artifact.zip"
        with open(zip_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        # Extract zip file
        app.logger.info(f"Extracting artifact to {dest_dir}")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(dest_dir)

        # Remove zip file
        zip_path.unlink()

        return True

    except Exception as e:
        app.logger.error(f"Error downloading artifact: {e}")
        return False


def validate_artifact_structure(artifact_dir: Path) -> bool:
    """Validate that artifact contains expected files and structure."""
    # Expected structure:
    # - allpaths-validation-cache.json (validation cache)
    # - allpaths-text/ directory with .txt files

    cache_file = artifact_dir / "allpaths-validation-cache.json"
    text_dir = artifact_dir / "allpaths-text"

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
        if txt_file.stat().st_size > 1024 * 1024:  # 1MB limit
            app.logger.error(f"Text file too large: {txt_file}")
            return False

    return True


def run_continuity_check(text_dir: Path, cache_file: Path, pr_number: int = None, progress_callback=None) -> dict:
    """Run the AI continuity checking script with optional progress callbacks."""
    try:
        app.logger.info(f"Running continuity checker on {text_dir}")

        # Call the checker function directly with progress callback
        results = check_paths_with_progress(text_dir, cache_file, progress_callback)

        return results

    except Exception as e:
        app.logger.error(f"Error running continuity checker: {e}", exc_info=True)
        return {
            "checked_count": 0,
            "paths_with_issues": [],
            "summary": f"Error: {str(e)}"
        }


def format_pr_comment(results: dict) -> str:
    """Format the continuity check results as a PR comment."""
    if results["checked_count"] == 0:
        return f"""## 🤖 AI Continuity Check

{results["summary"]}

_No new story paths to check._
"""

    # Build comment
    comment = f"""## 🤖 AI Continuity Check

**Summary:** {results["summary"]}

"""

    if not results["paths_with_issues"]:
        comment += "✅ **All paths passed continuity checks!**\n\n"
        comment += f"Checked {results['checked_count']} new path(s), no issues found.\n"
    else:
        comment += f"⚠️ **Found issues in {len(results['paths_with_issues'])} path(s)**\n\n"

        # Group by severity
        critical = [p for p in results["paths_with_issues"] if p["severity"] == "critical"]
        major = [p for p in results["paths_with_issues"] if p["severity"] == "major"]
        minor = [p for p in results["paths_with_issues"] if p["severity"] == "minor"]

        if critical:
            comment += f"### 🔴 Critical Issues ({len(critical)})\n\n"
            for path in critical:
                comment += format_path_issues(path)

        if major:
            comment += f"### 🟡 Major Issues ({len(major)})\n\n"
            for path in major:
                comment += format_path_issues(path)

        if minor:
            comment += f"### 🟢 Minor Issues ({len(minor)})\n\n"
            for path in minor:
                comment += format_path_issues(path)

    comment += "\n---\n_Powered by Ollama (gpt-oss:20b-fullcontext)_\n"

    return comment


def format_path_issues(path: dict) -> str:
    """Format issues for a single path."""
    route_str = " → ".join(path["route"]) if path["route"] else path["id"]
    output = f"**Path:** `{route_str}`\n\n"
    output += f"_{path['summary']}_\n\n"

    if path.get("issues"):
        output += "<details>\n<summary>Details</summary>\n\n"
        for issue in path["issues"]:
            issue_type = issue.get("type", "unknown")
            severity = issue.get("severity", "unknown")
            description = issue.get("description", "No description")
            location = issue.get("location", "")

            output += f"- **{issue_type.capitalize()}** ({severity}): {description}"
            if location:
                output += f" _{location}_"
            output += "\n"
        output += "\n</details>\n\n"

    return output


def post_pr_comment(pr_number: int, comment: str) -> bool:
    """Post a comment to a GitHub PR."""
    if not GITHUB_TOKEN:
        app.logger.error("GITHUB_TOKEN not set, cannot post comment")
        return False

    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues/{pr_number}/comments"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
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
    if not GITHUB_TOKEN:
        return None

    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/actions/runs/{workflow_run_id}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
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


def process_webhook_async(workflow_id, pr_number, artifacts_url):
    """Process webhook in background thread."""
    try:
        app.logger.info(f"[Background] Processing workflow {workflow_id} for PR #{pr_number}")

        # Track this job
        with metrics_lock:
            active_jobs[workflow_id] = {
                "pr_number": pr_number,
                "start_time": datetime.now(),
                "current_path": 0,
                "total_paths": 0,
                "status": "initializing"
            }
            metrics["total_webhooks_received"] += 1

        # Fetch artifact list
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
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

            # Validate structure
            if not validate_artifact_structure(tmpdir_path):
                app.logger.error("[Background] Invalid artifact structure")
                return

            # Get paths to check
            text_dir = tmpdir_path / "allpaths-text"
            cache_file = tmpdir_path / "allpaths-validation-cache.json"

            # Load cache to see what paths need checking
            cache = load_validation_cache(cache_file)
            unvalidated = get_unvalidated_paths(cache, text_dir)

            if not unvalidated:
                app.logger.info("[Background] No new paths to check")
                comment = """## 🤖 AI Continuity Check

No new story paths to check. All paths have been validated previously.

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

            path_list = "\n".join([f"- Path `{path_id}`" for path_id, _ in unvalidated])
            initial_comment = f"""## 🤖 AI Continuity Check - Starting

Found **{total_paths}** new story path(s) to check.

**Paths to validate:**
{path_list}

_This may take 5-10 minutes. Updates will be posted as each path completes._

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
                    route_str = " → ".join(path_result["route"]) if path_result["route"] else path_id
                    severity = path_result.get("severity", "none")
                    summary = path_result.get("summary", "")
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

**Path ID:** `{path_id}`
**Route:** `{route_str}`
**Result:** {severity}
**Summary:** {summary}
"""

                    # Add detailed issues if present
                    if issues:
                        update_comment += "\n<details>\n<summary>Details</summary>\n\n"
                        for issue in issues:
                            issue_type = issue.get("type", "unknown")
                            issue_severity = issue.get("severity", "unknown")
                            description = issue.get("description", "No description")
                            location = issue.get("location", "")

                            update_comment += f"- **{issue_type.capitalize()}** ({issue_severity}): {description}"
                            if location:
                                update_comment += f" _{location}_"
                            update_comment += "\n"
                        update_comment += "\n</details>\n"

                    # Add approval helper text
                    update_comment += f"\n💡 **To approve this path:** reply `/approve-path {path_id}`\n"

                    app.logger.info(f"[Background] Posting progress update: {current}/{total}")
                    post_pr_comment(pr_number, update_comment)
                except Exception as e:
                    app.logger.error(f"[Background] Error in progress callback: {e}", exc_info=True)

            # Run continuity check with progress callback
            results = run_continuity_check(text_dir, cache_file, pr_number, progress_callback)

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

    except Exception as e:
        app.logger.error(f"[Background] Error processing webhook: {e}", exc_info=True)

        # Mark job as failed
        with metrics_lock:
            if workflow_id in active_jobs:
                job_info = active_jobs.pop(workflow_id)
                job_info["status"] = "failed"
                job_info["error"] = str(e)
                job_info["end_time"] = datetime.now()
                job_info["duration_seconds"] = (job_info["end_time"] - job_info["start_time"]).total_seconds()
                job_history.append(job_info)
                if len(job_history) > 50:
                    job_history.pop(0)
                metrics["total_jobs_failed"] += 1


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

    # Spawn background thread to process webhook
    thread = threading.Thread(
        target=process_webhook_async,
        args=(workflow_id, pr_number, artifacts_url),
        daemon=True
    )
    thread.start()

    # Return immediately
    app.logger.info(f"Accepted webhook for PR #{pr_number}, processing in background")
    return jsonify({"message": "Webhook accepted, processing in background", "pr": pr_number}), 202


def handle_comment_webhook(payload):
    """Handle issue_comment webhooks for path approval."""
    action = payload.get('action')
    if action != 'created':
        return jsonify({"message": "Not a new comment"}), 200

    # Check if it's a PR (not an issue)
    if 'pull_request' not in payload.get('issue', {}):
        return jsonify({"message": "Not a PR comment"}), 200

    comment_body = payload['comment']['body']
    pr_number = payload['issue']['number']
    username = payload['comment']['user']['login']

    # Check for /approve-path command
    if not re.search(r'/approve-path\b', comment_body):
        return jsonify({"message": "Not an approval command"}), 200

    # Ignore bot's own progress comments (they contain the helper text)
    if '💡 **To approve this path:**' in comment_body:
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


def is_authorized(username: str) -> bool:
    """Check if user is a repo collaborator."""
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/collaborators/{username}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    try:
        response = requests.get(url, headers=headers)
        return response.status_code == 204  # 204 = is collaborator
    except Exception as e:
        app.logger.error(f"Error checking authorization: {e}")
        return False


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

            cache_file = tmpdir_path / "allpaths-validation-cache.json"
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

            if not commit_file_to_branch(branch_name, "dist/allpaths-validation-cache.json",
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
        app.logger.error(f"[Approval] Error: {e}", exc_info=True)
        post_pr_comment(pr_number, f"⚠️ Error processing approval: {str(e)}")


def get_pr_info(pr_number: int) -> Dict:
    """Get PR information from GitHub API."""
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/pulls/{pr_number}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
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
    # Get workflow runs for this PR
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/actions/runs"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
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
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
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
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{file_path}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
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
    except Exception as e:
        app.logger.error(f"Error committing file: {e}")
        return False


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    status = {
        "status": "ok",
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
