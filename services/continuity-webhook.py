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
from pathlib import Path
from flask import Flask, request, jsonify
import requests

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


def run_continuity_check(text_dir: Path, cache_file: Path) -> dict:
    """Run the AI continuity checking script."""
    try:
        app.logger.info(f"Running continuity checker on {text_dir}")
        result = subprocess.run(
            [sys.executable, str(CHECKER_SCRIPT), str(text_dir), str(cache_file)],
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout (ollama can be slow)
        )

        # Parse JSON output from script
        try:
            # The script outputs JSON to stdout
            output_lines = result.stdout.strip().split('\n')
            # Find the JSON output (should be after "=== RESULTS ===")
            json_start = -1
            for i, line in enumerate(output_lines):
                if line == "=== RESULTS ===":
                    json_start = i + 1
                    break

            if json_start >= 0 and json_start < len(output_lines):
                json_output = '\n'.join(output_lines[json_start:])
                return json.loads(json_output)
            else:
                # Fallback: try to parse entire stdout as JSON
                return json.loads(result.stdout)

        except json.JSONDecodeError as e:
            app.logger.error(f"Failed to parse checker output: {e}")
            app.logger.error(f"Stdout: {result.stdout}")
            app.logger.error(f"Stderr: {result.stderr}")
            return {
                "checked_count": 0,
                "paths_with_issues": [],
                "summary": f"Error: Failed to parse checker output"
            }

    except subprocess.TimeoutExpired:
        app.logger.error("Continuity checker timed out")
        return {
            "checked_count": 0,
            "paths_with_issues": [],
            "summary": "Error: Checker timed out after 10 minutes"
        }
    except Exception as e:
        app.logger.error(f"Error running continuity checker: {e}")
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

    # Only handle workflow_run events
    if event_type != 'workflow_run':
        return jsonify({"message": "Event ignored"}), 200

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

    # Get artifacts
    artifacts_url = workflow_run.get('artifacts_url')
    if not artifacts_url:
        app.logger.error("No artifacts URL in workflow")
        return jsonify({"error": "No artifacts URL"}), 400

    # Fetch artifact list
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    try:
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
            app.logger.info("No allpaths artifact found, nothing to check")
            return jsonify({"message": "No allpaths artifact"}), 200

        # Download and process artifact
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Download artifact
            artifact_url = allpaths_artifact['archive_download_url']
            if not download_artifact(artifact_url, tmpdir_path):
                return jsonify({"error": "Failed to download artifact"}), 500

            # Validate structure
            if not validate_artifact_structure(tmpdir_path):
                return jsonify({"error": "Invalid artifact structure"}), 400

            # Run continuity check
            text_dir = tmpdir_path / "allpaths-text"
            cache_file = tmpdir_path / "allpaths-validation-cache.json"

            results = run_continuity_check(text_dir, cache_file)

            # Format and post comment
            comment = format_pr_comment(results)
            if not post_pr_comment(pr_number, comment):
                return jsonify({"error": "Failed to post comment"}), 500

        return jsonify({"message": "Continuity check completed", "pr": pr_number}), 200

    except Exception as e:
        app.logger.error(f"Error processing webhook: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


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
