# Azure Deployment Fixes

**Date:** January 23, 2026

## Issues Fixed

### 1. WebSocket Connection Problem ❌ → ✅

**Problem:** The website was using hardcoded `ws://` protocol and port `:8000`

**Fixed in:**

- `static/index_4esp.html` - WebSocket connection
- `static/index.html` - Static file paths

**Changes:**

```javascript
// OLD (Broken on Azure)
const wsUrl = `ws://${window.location.hostname}:8000/ws/frontend`;

// NEW (Works on Azure)
const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const wsUrl = `${protocol}//${window.location.host}/ws/frontend`;
```

**Why this works:**

- `wss://` for HTTPS (Azure uses HTTPS)
- `ws://` for HTTP (local development)
- `window.location.host` includes the port automatically
- No hardcoded port 8000

### 2. Static File Paths Problem ❌ → ✅

**Problem:** CSS and JS files referenced with relative paths

**Fixed in:**

- `static/index.html`
- `static/index_4esp.html`

**Changes:**

```html
<!-- OLD -->
<link rel="stylesheet" href="style.css" />
<script src="app.js"></script>

<!-- NEW -->
<link rel="stylesheet" href="/style.css" />
<script src="/app.js"></script>
```

**Why this works:**

- Absolute paths (`/style.css`) work with FastAPI routes
- Backend serves these at `/style.css` and `/app.js`

## Deployment Checklist for Azure

### ✅ Pre-Deployment

- [x] WebSocket uses `wss://` for HTTPS
- [x] WebSocket uses `window.location.host` (not hardcoded hostname)
- [x] Static files use absolute paths (`/style.css` not `style.css`)
- [ ] Environment variables set in Azure:
  - `COSMOS_ENDPOINT`
  - `COSMOS_KEY`
  - `COSMOS_DATABASE`
  - `COSMOS_CONTAINER`

### ✅ Testing Azure Deployment

1. **Open browser console** (F12)
2. **Check WebSocket connection:**
   ```
   🔌 Connecting to: wss://your-site.azurewebsites.net/ws/frontend
   ✓ WebSocket connected!
   ```
3. **Verify static files load:**
   - No 404 errors for CSS/JS
   - Page styling appears correctly
4. **Test game functionality:**
   - Master ESP connects
   - Tiles register
   - Pattern displays
   - Game plays correctly

### 🔍 Debugging on Azure

If website still doesn't work:

1. **Check Browser Console (F12)**
   - Look for WebSocket errors
   - Check for 404 errors on static files
   - Verify correct protocol (wss:// for Azure)

2. **Check Azure App Service Logs**

   ```bash
   az webapp log tail --name your-app-name --resource-group your-rg
   ```

3. **Test Backend Health**
   - Visit: `https://your-site.azurewebsites.net/status`
   - Should return JSON with system status

4. **Common Issues:**
   - **"WebSocket connection failed"** → Check if App Service has WebSockets enabled
   - **"404 on /app.js"** → Files not deployed to `static/` folder
   - **"Master not connecting"** → Master ESP must use `wss://` and correct hostname

### 🔧 Azure App Service Configuration

Enable WebSockets in Azure:

```bash
az webapp config set --name your-app-name --resource-group your-rg --web-sockets-enabled true
```

Or via Azure Portal:

1. Go to your App Service
2. Settings → Configuration → General settings
3. **Web sockets:** ON
4. Save

## URLs After Deployment

### For Players (Website)

- Main site: `https://memo-motion.azurewebsites.net/`
- 4-ESP version: `https://memo-motion.azurewebsites.net/static/index_4esp.html`
- Leaderboard API: `https://memo-motion.azurewebsites.net/api/leaderboard`
- Health check: `https://memo-motion.azurewebsites.net/status`

### For Master ESP (Firmware)

Update master ESP firmware:

```cpp
const char* WS_HOST = "memo-motion.azurewebsites.net";
const uint16_t WS_PORT = 443;  // HTTPS port
```

WebSocket endpoint remains: `/ws/master`

## File Changes Summary

| File                     | Changes                               | Purpose                  |
| ------------------------ | ------------------------------------- | ------------------------ |
| `static/index.html`      | CSS/JS absolute paths + debug logging | Load resources correctly |
| `static/index_4esp.html` | WebSocket protocol detection + paths  | Connect via WSS on Azure |
| `static/app.js`          | _(Already correct)_                   | Auto-detects WSS         |

## Verification

After deploying to Azure, verify:

```bash
# 1. Check website loads
curl https://memo-motion.azurewebsites.net/

# 2. Check WebSocket endpoint exists
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" \
  https://memo-motion.azurewebsites.net/ws/frontend

# 3. Check master endpoint
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" \
  https://memo-motion.azurewebsites.net/ws/master

# 4. Check API
curl https://memo-motion.azurewebsites.net/api/stats
```

## Next Steps

1. **Deploy to Azure** (push changes to Git)
2. **Enable WebSockets** in App Service settings
3. **Set environment variables** for Cosmos DB
4. **Update Master ESP** with Azure hostname
5. **Test full flow** from registration to gameplay

## Support

If issues persist:

- Check Azure App Service logs
- Verify WebSockets are enabled
- Test WebSocket connection with browser dev tools
- Ensure static files are deployed to `static/` folder
