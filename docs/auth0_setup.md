# Auth0 Setup Guide

TrendWatch uses Auth0 for Google OAuth authentication. This guide covers creating an Auth0 application and configuring it for TrendWatch.

## Prerequisites

- A domain pointing to your server (e.g. `app.trendwatch2k10.com`)
- TrendWatch running via Docker Compose
- A Google account for testing

## 1. Create an Auth0 Account

1. Go to [auth0.com](https://auth0.com) and sign up (free tier is sufficient)
2. Complete the onboarding wizard — choose your tenant domain (e.g. `trendwatch.eu.auth0.com`)

## 2. Create an Application

1. In the Auth0 dashboard, go to **Applications → Applications**
2. Click **Create Application**
3. Name: `TrendWatch` (or any name)
4. Type: **Regular Web Application**
5. Click **Create**

## 3. Configure Allowed URLs

In the application's **Settings** tab, configure:

| Field | Value |
|-------|-------|
| **Allowed Callback URLs** | `https://your-domain.com/auth/callback` |
| **Allowed Logout URLs** | `https://your-domain.com` |
| **Allowed Web Origins** | `https://your-domain.com` |

> ⚠️ The callback URL must match **exactly** (protocol, domain, port, path). A mismatch causes "Callback URL mismatch" errors.

## 4. Enable Google Social Login

1. Go to **Authentication → Social**
2. Click **Google / Gmail**
3. Toggle to **Enable**
4. For development: use Auth0's default dev keys (built-in)
5. For production: create a Google OAuth app at [console.cloud.google.com](https://console.cloud.google.com) and paste the Client ID + Secret

## 5. Configure .env

Copy the credentials from the Auth0 application's Settings tab:

```env
AUTH0_DOMAIN=trendwatch.eu.auth0.com
AUTH0_CLIENT_ID=your_client_id_here
AUTH0_CLIENT_SECRET=your_client_secret_here
AUTH0_CALLBACK_URL=https://your-domain.com/auth/callback
```

## 6. Configure Access Roles

TrendWatch has two roles — set via email lists in `.env`:

```env
# Admin users — full access (import, fetch, admin panel)
ADMIN_EMAILS=you@gmail.com,colleague@gmail.com

# Viewer users — read-only dashboard (leave empty to allow all authenticated Google accounts)
ALLOWED_EMAILS=friend@gmail.com,client@gmail.com
```

If `ALLOWED_EMAILS` is empty, any Google account that can authenticate through Auth0 gets viewer access.

## 7. Apply and Restart

After editing `.env`:

```bash
docker compose down web
docker compose up -d web
docker compose logs -f web
```

## Troubleshooting

### "Callback URL mismatch"
- The URL in `AUTH0_CALLBACK_URL` does not match what's configured in Auth0 Dashboard
- Check for trailing slashes, http vs https, or port differences

### "Access denied" after login
- The user's email is not in `ADMIN_EMAILS` or `ALLOWED_EMAILS`
- Add their email and restart the web container

### Session lost on restart
- `SESSION_SECRET` must be a stable random string (32+ characters)
- Regenerating it invalidates all active sessions

## Auth0 Action (optional)

The file `docs/auth0_action.js` contains a post-login action that enriches the user token with role metadata. Deploy it in **Auth0 Dashboard → Actions → Flows → Login** if you want roles reflected in the JWT for external integrations.
