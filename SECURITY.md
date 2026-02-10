# 🔒 Security Guide

## Security Features Implemented

### ✅ Input Validation
- **Query sanitization** - Removes dangerous characters (`<>'";\``)
- **Length limits** - Max 500 chars for inputs
- **Pattern matching** - Only alphanumeric, spaces, hyphens allowed
- **Category whitelist** - Only predefined categories accepted

### ✅ Rate Limiting
- **API endpoints protected** with different limits:
  - GET endpoints: 100/hour
  - Add product: 10/hour (expensive operation)
  - Check prices: 5/hour (very expensive)
  - Health check: 60/minute

### ✅ CORS Protection
- **Restricted origins** - Only allowed domains can access API
- Configure via `ALLOWED_ORIGINS` environment variable
- Default: `http://localhost:5173` (development only)

### ✅ Security Headers
All responses include:
- `X-Content-Type-Options: nosniff` - Prevents MIME sniffing
- `X-Frame-Options: DENY` - Prevents clickjacking
- `X-XSS-Protection: 1; mode=block` - XSS protection
- `Strict-Transport-Security` - Forces HTTPS
- `Content-Security-Policy` - Restricts resource loading

### ✅ Database Security
- **Parameterized queries** - Prevents SQL injection
- **No raw SQL** from user input
- **Connection management** - Proper cleanup

### ✅ Error Handling
- **No sensitive data in errors** - Generic messages to users
- **Detailed logging** - Internal logs for debugging
- **Exception catching** - Prevents crashes

### ✅ Request Size Limits
- Max request size: **16KB**
- Prevents large payload attacks

## 🚀 Deployment Security

### Development
```bash
# Copy environment template
cp .env.example .env

# Generate secure secret key
python -c "import secrets; print(secrets.token_hex(32))"

# Add to .env
SECRET_KEY=<generated-key>

# Run secure API
python api_secure.py
```

### Production Checklist

#### 1. Environment Variables
```bash
# Required in production
export FLASK_ENV=production
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
export ALLOWED_ORIGINS=https://your-domain.com
export DATABASE_PATH=/var/data/prices.db
```

#### 2. Use Production Server
```bash
# Install
pip install gunicorn

# Run with gunicorn (NOT Flask dev server)
gunicorn -w 4 -b 127.0.0.1:5000 api_secure:app
```

#### 3. HTTPS/SSL
```bash
# Get SSL certificate (Let's Encrypt)
sudo certbot certonly --standalone -d your-domain.com

# Use with nginx or gunicorn
gunicorn --certfile=/path/to/cert.pem \
         --keyfile=/path/to/key.pem \
         -b 0.0.0.0:443 \
         api_secure:app
```

#### 4. Reverse Proxy (Nginx)
```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # Security headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

#### 5. Firewall Rules
```bash
# Allow only necessary ports
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable
```

#### 6. Database Permissions
```bash
# Restrict database file permissions
chmod 600 prices.db
chown www-data:www-data prices.db
```

#### 7. Monitoring & Logging
```bash
# Log rotation
sudo nano /etc/logrotate.d/price-tracker

# Add:
/var/log/price-tracker/*.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    missingok
}
```

## 🛡️ Additional Recommendations

### 1. Authentication (Optional)
If you want to restrict API access:

```python
# Add to api_secure.py
from functools import wraps

def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if api_key != os.environ.get('API_KEY'):
            abort(401)
        return f(*args, **kwargs)
    return decorated

@app.route('/api/products', methods=['POST'])
@require_api_key  # Add this
def add_product():
    ...
```

### 2. Database Backup
```bash
# Automated backups
0 2 * * * cp /var/data/prices.db /var/backups/prices-$(date +\%Y\%m\%d).db
```

### 3. Update Dependencies Regularly
```bash
# Check for security updates
pip list --outdated

# Update
pip install --upgrade flask flask-cors playwright
```

### 4. Web Application Firewall
Consider using:
- **Cloudflare** - DDoS protection, WAF
- **AWS WAF** - If hosting on AWS
- **ModSecurity** - Open-source WAF

### 5. Security Scanning
```bash
# Install safety
pip install safety

# Check for vulnerabilities
safety check

# Or use
pip-audit
```

## ⚠️ Security Considerations

### What's Protected ✅
- SQL injection
- XSS attacks
- CSRF (with proper headers)
- Rate limiting abuse
- Large payload attacks
- Information disclosure

### What Needs Additional Work ⚠️
- **Authentication** - No user login system
- **Authorization** - Anyone can add products
- **API keys** - No API key requirement
- **Audit logging** - No detailed audit trail

### Known Limitations
- **Scraping detection** - Some sites may block headless browsers
- **Rate limits** - Memory-based (resets on restart)
- **File upload** - Not implemented (if added, needs validation)

## 📞 Incident Response

If you detect suspicious activity:

1. **Check logs**: `tail -f api.log`
2. **Block IP**: Add to firewall
3. **Review rate limits**: Adjust if needed
4. **Update secrets**: Rotate `SECRET_KEY`
5. **Check database**: Look for anomalies

## 🔄 Regular Maintenance

- [ ] Review logs weekly
- [ ] Update dependencies monthly
- [ ] Backup database daily
- [ ] Check for failed login attempts
- [ ] Monitor API usage patterns
- [ ] Review and rotate secrets quarterly

---

**Remember**: Security is a process, not a product. Keep everything updated!
