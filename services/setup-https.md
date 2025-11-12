# HTTPS Setup for Webhook Service

The webhook service needs to be accessible via HTTPS for GitHub to send webhooks. You have two main options:

## Prerequisites

- Domain name pointing to this server (158.101.115.41)
- Firewall configured to allow inbound HTTPS (port 443)
- Webhook service running on localhost:5000

## Option 1: Caddy (Recommended - Easiest)

Caddy automatically handles HTTPS certificate generation and renewal.

### Install Caddy

```bash
# Install Caddy
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy
```

### Configure Caddy

Create `/etc/caddy/Caddyfile`:

```caddy
# Replace with your actual domain
your-domain.com {
    # Reverse proxy to webhook service
    reverse_proxy /webhook localhost:5000

    # Health check endpoint
    reverse_proxy /health localhost:5000
}
```

### Start Caddy

```bash
sudo systemctl enable caddy
sudo systemctl start caddy
sudo systemctl status caddy
```

Caddy will automatically:
- Obtain Let's Encrypt certificate
- Configure HTTPS
- Renew certificates automatically

Your webhook URL will be: `https://your-domain.com/webhook`

---

## Option 2: Nginx + Certbot

More manual but widely used.

### Install Nginx and Certbot

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
```

### Configure Nginx

Create `/etc/nginx/sites-available/continuity-webhook`:

```nginx
server {
    listen 80;
    server_name your-domain.com;  # Replace with your domain

    location /webhook {
        proxy_pass http://localhost:5000/webhook;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Important: Preserve webhook signature header
        proxy_pass_request_headers on;
    }

    location /health {
        proxy_pass http://localhost:5000/health;
        proxy_set_header Host $host;
    }
}
```

### Enable Site

```bash
sudo ln -s /etc/nginx/sites-available/continuity-webhook /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Get SSL Certificate

```bash
sudo certbot --nginx -d your-domain.com
```

Certbot will:
- Automatically modify nginx config for HTTPS
- Set up auto-renewal

Your webhook URL will be: `https://your-domain.com/webhook`

---

## Option 3: Production WSGI Server (No Reverse Proxy)

If you want to run the Flask app directly with HTTPS (not recommended):

### Install Gunicorn + gevent

```bash
source /home/ubuntu/Code/NaNoWriMo2025/services/venv/bin/activate
pip install gunicorn gevent
```

### Run with Gunicorn

```bash
gunicorn -w 4 -b 0.0.0.0:8000 continuity-webhook:app
```

But you'll still need nginx/caddy for HTTPS termination.

---

## Testing HTTPS Setup

### 1. Check Certificate

```bash
curl -I https://your-domain.com/health
```

Should return HTTP 200 with valid certificate.

### 2. Test from GitHub's Perspective

Use GitHub's webhook test feature:
- Go to repository settings → Webhooks
- Click on your webhook
- Click "Redeliver" on a test delivery

### 3. Check Logs

**Webhook service:**
```bash
sudo journalctl -u continuity-webhook -f
```

**Caddy:**
```bash
sudo journalctl -u caddy -f
```

**Nginx:**
```bash
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

---

## Firewall Configuration

### Open Port 443 (HTTPS)

**UFW:**
```bash
sudo ufw allow 443/tcp
sudo ufw status
```

**iptables:**
```bash
sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT
```

### Optional: Open Port 80 (HTTP) for Certificate Validation

```bash
sudo ufw allow 80/tcp
```

Port 80 is needed for Let's Encrypt certificate validation, but traffic will redirect to HTTPS.

---

## DNS Configuration

Point your domain to this server:

**A Record:**
```
Type: A
Name: continuity (or @ for root domain)
Value: 158.101.115.41
TTL: 3600
```

**Verify DNS:**
```bash
dig your-domain.com +short
# Should return: 158.101.115.41

nslookup your-domain.com
```

---

## Troubleshooting

### Certificate Issues

**Caddy:**
- Check logs: `sudo journalctl -u caddy -n 50`
- Verify domain points to server: `dig your-domain.com`
- Ensure port 80 and 443 are open

**Certbot:**
- Test certificate: `sudo certbot certificates`
- Renew manually: `sudo certbot renew --dry-run`

### Webhook Not Receiving Events

1. Check service is running:
   ```bash
   sudo systemctl status continuity-webhook
   curl http://localhost:5000/health
   ```

2. Check reverse proxy:
   ```bash
   curl https://your-domain.com/health
   ```

3. Check GitHub webhook deliveries:
   - Repository Settings → Webhooks → Recent Deliveries
   - Look for error codes (500, 401, etc.)

4. Check signature verification:
   - Ensure `WEBHOOK_SECRET` matches GitHub webhook secret
   - Check webhook service logs for signature errors

### Connection Refused

- Verify webhook service is running: `sudo systemctl status continuity-webhook`
- Verify it's listening on port 5000: `sudo netstat -tlnp | grep 5000`
- Check firewall: `sudo ufw status`

---

## Security Checklist

- [ ] HTTPS enabled (valid certificate)
- [ ] Webhook secret configured (in both GitHub and env file)
- [ ] Signature verification enabled (check service logs)
- [ ] Service runs as non-root user (ubuntu)
- [ ] Environment file has restricted permissions (600)
- [ ] Firewall allows only necessary ports (443, optionally 80)
- [ ] Regular updates: `sudo apt update && sudo apt upgrade`

---

## Recommended: Caddy Setup (Quick Guide)

For the fastest setup:

```bash
# 1. Install Caddy
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy

# 2. Configure Caddy
sudo nano /etc/caddy/Caddyfile
# Add:
#   your-domain.com {
#       reverse_proxy /webhook localhost:5000
#       reverse_proxy /health localhost:5000
#   }

# 3. Start services
sudo systemctl start continuity-webhook
sudo systemctl enable continuity-webhook
sudo systemctl restart caddy

# 4. Test
curl https://your-domain.com/health
```

Done! Your webhook URL is: `https://your-domain.com/webhook`
