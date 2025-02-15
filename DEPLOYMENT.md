FLASK_ENV=production
   FLASK_SECRET_KEY=[your-secret-key]
   FIRECRAWL_API_KEY=[your-key]
   GEMINI_API_KEY=[your-key]
   FIREBASE_CREDENTIALS=[your-credentials-json]
   ```

## GitHub Setup

1. Create a new GitHub repository:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin [your-repo-url]
   git push -u origin main
   ```

2. Add GitHub Secrets:
   - Go to your repository's Settings > Secrets and variables > Actions
   - Add the following secrets:
     * SSH_HOST: Your server's hostname
     * SSH_USERNAME: SSH username
     * SSH_PRIVATE_KEY: Your SSH private key for server access
     * FIREBASE_CREDENTIALS: Your Firebase credentials JSON

   To generate an SSH key pair:
   ```bash
   ssh-keygen -t ed25519 -C "your_email@example.com"
   # Copy public key to your server's authorized_keys
   ssh-copy-id -i ~/.ssh/id_ed25519.pub username@your-server
   # Copy private key content to GitHub SSH_PRIVATE_KEY secret
   cat ~/.ssh/id_ed25519
   ```

## Deployment Steps

1. Initial Server Setup:
   ```bash
   # Create application directory
   sudo mkdir -p /path/to/app
   sudo chown www-data:www-data /path/to/app
   ```

2. Set up Systemd Service:
   ```bash
   # Copy systemd service file
   sudo cp deployment/parkrun-story.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable parkrun-story
   ```

3. Firebase Configuration:
   - Go to Firebase Console
   - Add your domain (parkrun.[yourdomain].com) to Authorized Domains
   - Update security rules to allow your domain
   - Under Authentication > Sign-in methods, add your production domain

4. Web Server Configuration (Nginx example):
   ```nginx
   # Rate limiting zone
   limit_req_zone $binary_remote_addr zone=parkrun_limit:10m rate=10r/s;

   server {
       listen 80;
       server_name parkrun.[yourdomain].com;

       # Redirect HTTP to HTTPS
       return 301 https://$server_name$request_uri;
   }

   server {
       listen 443 ssl http2;
       server_name parkrun.[yourdomain].com;

       # SSL configuration
       ssl_certificate /path/to/cert.pem;
       ssl_certificate_key /path/to/key.pem;
       ssl_protocols TLSv1.2 TLSv1.3;
       ssl_ciphers HIGH:!aNULL:!MD5;

       # Security headers
       add_header X-Frame-Options "SAMEORIGIN";
       add_header X-XSS-Protection "1; mode=block";
       add_header X-Content-Type-Options "nosniff";
       add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
       add_header Content-Security-Policy "default-src 'self' https://www.gstatic.com https://apis.google.com; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://www.gstatic.com; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdn.replit.com; img-src 'self' data: https:; font-src 'self' https://cdn.jsdelivr.net data:;";

       # Rate limiting
       limit_req zone=parkrun_limit burst=20 nodelay;

       location / {
           proxy_pass http://localhost:5000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;

           # WebSocket support
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";

           # Timeouts
           proxy_connect_timeout 60;
           proxy_send_timeout 60;
           proxy_read_timeout 60;
       }

       # Cache static files
       location /static/ {
           expires 30d;
           add_header Cache-Control "public, no-transform";
       }
   }
   ```

## Security Considerations

1. Always use HTTPS in production
2. Keep your environment variables secure
3. Regularly update dependencies
4. Monitor Firebase usage and costs
5. Set up proper logging and monitoring

## Continuous Deployment

The application uses GitHub Actions for automated deployment:

1. Push your changes to the `main` branch:
   ```bash
   git push origin main
   ```

2. Monitor deployment:
   - Check Actions tab in GitHub repository
   - Review deployment logs for any issues
   - Verify application functionality after deployment

3. Rollback if needed:
   ```bash
   # On your server
   cd /path/to/app
   git reset --hard HEAD^
   sudo systemctl restart parkrun-story