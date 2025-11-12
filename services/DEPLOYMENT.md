# Deployment Checklist for AI Continuity Checking

Follow these steps to deploy the webhook service for automated story continuity checking.

## Current Status

✅ **Completed:**
- [x] Webhook service created (`continuity-webhook.py`)
- [x] AI checking script created (`check-story-continuity.py`)
- [x] Systemd service configured
- [x] Environment file created (`~/.config/continuity-webhook/env`)
- [x] GitHub workflow updated to upload artifacts
- [x] Documentation written

⏳ **Remaining:**
- [ ] Set up HTTPS (domain + Caddy/Nginx)
- [ ] Start webhook service
- [ ] Configure firewall
- [ ] Add webhook to GitHub repository
- [ ] Test with a live PR

---

## Step-by-Step Deployment

### Step 1: Choose Your Domain

You need a domain or subdomain pointing to this server (158.101.115.41).

**Options:**
- Use existing domain: `continuity.yourdomain.com`
- Use server hostname: TBD (check with your hosting provider)
- Set up new subdomain

**Action:** Configure DNS A record:
```
Type: A
Name: continuity (or your chosen subdomain)
Value: 158.101.115.41
TTL: 3600
```

**Verify:**
```bash
dig continuity.yourdomain.com +short
# Should return: 158.101.115.41
```

---

### Step 2: Set Up HTTPS

**Recommended: Caddy (automatic HTTPS)**

See `setup-https.md` for detailed instructions. Quick version:

```bash
# Install Caddy
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | \
  sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | \
  sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy

# Configure Caddy
sudo tee /etc/caddy/Caddyfile > /dev/null <<EOF
continuity.yourdomain.com {
    reverse_proxy /webhook localhost:5000
    reverse_proxy /health localhost:5000
}
EOF

# Start Caddy
sudo systemctl enable caddy
sudo systemctl start caddy
```

**Check status:**
```bash
sudo systemctl status caddy
```

---

### Step 3: Start Webhook Service

```bash
# Start the service
sudo systemctl start continuity-webhook

# Enable auto-start on boot
sudo systemctl enable continuity-webhook

# Check status
sudo systemctl status continuity-webhook

# View logs
sudo journalctl -u continuity-webhook -f
```

**Expected output:**
```
Starting webhook service on port 5000...
Repository: michaelansel/NaNoWriMo2025
Checker script: /home/ubuntu/Code/NaNoWriMo2025/scripts/check-story-continuity.py
```

---

### Step 4: Test Locally

Before opening firewall, test that everything works internally:

```bash
# Test health endpoint (local)
curl http://localhost:5000/health

# Expected: {"status":"ok","github_token_set":true,"webhook_secret_set":true,"checker_script_exists":true}

# Test health endpoint (through reverse proxy)
curl https://continuity.yourdomain.com/health

# Should also return 200 OK with valid HTTPS cert
```

---

### Step 5: Configure Firewall

**On this server (if using UFW):**
```bash
sudo ufw allow 443/tcp
sudo ufw allow 80/tcp  # For Let's Encrypt validation
sudo ufw status
```

**Off-host firewall:**
- Open port 443 (HTTPS) to 158.101.115.41
- Optionally open port 80 (for Let's Encrypt, can close after)

**Test external access:**
```bash
# From your local machine:
curl https://continuity.yourdomain.com/health
```

---

### Step 6: Add Webhook to GitHub

1. **Go to repository settings:**
   - https://github.com/michaelansel/NaNoWriMo2025/settings/hooks

2. **Click "Add webhook"**

3. **Configure:**
   - **Payload URL**: `https://continuity.yourdomain.com/webhook`
   - **Content type**: `application/json`
   - **Secret**: Get from `cat ~/.config/continuity-webhook/env | grep WEBHOOK_SECRET`
   - **SSL verification**: Enable SSL verification (recommended)
   - **Events**: "Workflow runs" only
   - **Active**: ✓

4. **Save webhook**

5. **Test webhook:**
   - GitHub will send a test ping
   - Check "Recent Deliveries" tab
   - Should see green checkmark (200 response)

---

### Step 7: Test with a PR

Create a test PR to verify end-to-end flow:

```bash
# Create test branch
cd /home/ubuntu/Code/NaNoWriMo2025
git checkout -b test-continuity-webhook

# Make a small change
echo "\n# Continuity checking test" >> README.md
git add README.md
git commit -m "Test: trigger continuity checking webhook"
git push origin test-continuity-webhook

# Open PR on GitHub
gh pr create --title "Test: AI Continuity Checking" --body "Testing webhook integration"
```

**Monitor the workflow:**
1. Go to https://github.com/michaelansel/NaNoWriMo2025/actions
2. Wait for workflow to complete
3. Watch webhook service logs: `sudo journalctl -u continuity-webhook -f`

**Expected behavior:**
1. Workflow builds story paths
2. Uploads allpaths artifact
3. Workflow completes
4. GitHub sends webhook to your service
5. Service downloads artifact
6. Service runs AI continuity check
7. Service posts comment to PR with results

**Check PR comments:**
- Should see comment from `github-actions[bot]` or your account (depending on token)
- Comment should show continuity check results

---

### Step 8: Verify and Clean Up

**Success criteria:**
- ✅ PR has continuity check comment
- ✅ No errors in service logs
- ✅ GitHub webhook shows successful delivery

**Clean up test PR:**
```bash
# Close and delete test PR if successful
gh pr close test-continuity-webhook
git checkout main
git branch -D test-continuity-webhook
git push origin --delete test-continuity-webhook
```

---

## Monitoring and Maintenance

### Check Service Status

```bash
sudo systemctl status continuity-webhook
```

### View Logs

```bash
# Recent logs
sudo journalctl -u continuity-webhook -n 100

# Follow logs (live)
sudo journalctl -u continuity-webhook -f

# Filter for errors
sudo journalctl -u continuity-webhook | grep -i error
```

### Restart Service

```bash
sudo systemctl restart continuity-webhook
```

### Update Service

If you modify the code:

```bash
cd /home/ubuntu/Code/NaNoWriMo2025
git pull origin main
sudo systemctl restart continuity-webhook
sudo journalctl -u continuity-webhook -f
```

---

## Troubleshooting

### Webhook Not Triggered

**Check GitHub webhook deliveries:**
1. Go to Settings → Webhooks → Your webhook
2. Click on webhook
3. View "Recent Deliveries"
4. Check response codes and body

**Common issues:**
- 401: Signature verification failed (check secrets match)
- 404: URL wrong (check domain and `/webhook` path)
- 500: Service error (check logs: `sudo journalctl -u continuity-webhook -n 50`)
- Timeout: Service not responding (check it's running)

### Service Won't Start

```bash
# Check logs
sudo journalctl -u continuity-webhook -n 50

# Common issues:
# - GITHUB_TOKEN not set
# - WEBHOOK_SECRET not set
# - Checker script not found
# - Port 5000 already in use
```

### No PR Comment Posted

**Check:**
1. GitHub token has correct permissions (repo scope)
2. Token is not expired
3. Service logs show "Posted comment to PR #X"
4. PR number was correctly identified

**Debug:**
```bash
# Check if token is valid
curl -H "Authorization: token YOUR_TOKEN" https://api.github.com/user

# Should return your user info, not 401
```

### AI Checking Takes Too Long

Ollama can be slow. Each path takes 30-120 seconds.

**Monitor:**
```bash
# Watch ollama usage
htop  # Look for ollama process

# Check ollama is responding
ollama run gpt-oss:20b-fullcontext "test"
```

### HTTPS Certificate Issues

**Caddy:**
```bash
sudo journalctl -u caddy -n 50
```

**Common issues:**
- Domain doesn't point to server (check DNS)
- Port 80/443 blocked (check firewall)
- Rate limit hit (Let's Encrypt: 5 certs per domain per week)

---

## Security Notes

### Rotate Secrets

If webhook secret is compromised:

```bash
# Generate new secret
NEW_SECRET=$(openssl rand -hex 32)

# Update env file
nano ~/.config/continuity-webhook/env
# Update WEBHOOK_SECRET

# Restart service
sudo systemctl restart continuity-webhook

# Update GitHub webhook settings with new secret
```

### Rotate GitHub Token

If GitHub token is compromised:

1. Revoke old token: https://github.com/settings/tokens
2. Generate new token with `repo` scope
3. Update env file: `nano ~/.config/continuity-webhook/env`
4. Restart service: `sudo systemctl restart continuity-webhook`

### Monitor Access

```bash
# Watch webhook access
sudo journalctl -u continuity-webhook -f | grep "webhook"

# Watch reverse proxy access (Caddy)
sudo journalctl -u caddy -f

# Or Nginx
sudo tail -f /var/log/nginx/access.log
```

---

## Next Steps

Once everything is working:

1. **Monitor for a few days** to ensure stability
2. **Review first few PR comments** to see if AI feedback is useful
3. **Tune the prompt** if needed (edit `scripts/check-story-continuity.py`)
4. **Document learnings** in project README
5. **Consider enhancements:**
   - Custom prompts per project
   - Integration with GitHub status checks
   - Dashboard for viewing check history
   - Support for multiple models

---

## Support

If you encounter issues:

1. Check logs: `sudo journalctl -u continuity-webhook -f`
2. Verify setup: `curl http://localhost:5000/health`
3. Test Ollama: `ollama run gpt-oss:20b-fullcontext "test"`
4. Review GitHub webhook deliveries
5. Check service documentation in `services/README.md`

---

## Summary

You now have an automated AI-powered continuity checking system that:
- ✅ Runs on every PR automatically
- ✅ Only checks new/modified story paths (efficient)
- ✅ Uses local Ollama (no API costs)
- ✅ Posts findings as PR comments (non-blocking warnings)
- ✅ Secure (webhook signature verification, no code execution)
- ✅ Maintainable (systemd service, logs, health checks)

Happy writing! 📖✨
