# Putting DeTour on the internet

Two pieces: the **server** (Python, on Render, free) and the **website** (static, on Vercel, free). The server must be up first, because the website needs its address.

## 1. The server on Render

1. Sign in at render.com with GitHub, then **New > Blueprint** and choose this repository. Render reads `render.yaml`.
2. Wait for the first deploy. Open `https://<your-service>.onrender.com/health`. It should answer `{"status":"ok",...}`.
3. In the service's **Environment** tab, set `OPENAI_API_KEY` so typed reports are read by the language model (and checked by the rule reader). Without it the rule reader works alone. `ELEVENLABS_API_KEY` turns on the ElevenLabs voice, speech-to-text and the in-browser call agent; without it the browser's own voice is used and the call is settled with buttons.

Free services sleep when idle, and the first request after that takes up to a minute. Open `/health` a few minutes before showing anyone.

State is kept in memory. A restart (or the idle sleep) returns the app to the starting demo, which is also what **Reset demo** does.

## 2. The website on Vercel

1. **Add New > Project**, import this repository.
2. Set **Root Directory** to `frontend`. Vercel detects Vite.
3. Add the environment variable `VITE_API_BASE` = the Render address, with no trailing slash.
4. Deploy. Pages: `/` (home), `/dispatch`, `/head`, `/driver?as=Meera`.

After changing `VITE_API_BASE`, redeploy: it is baked into the build.

## Checks
- Open the site, choose **Open the dispatcher**, press **Reset demo**. The board should fill in and show "Live".
- If it says "Reconnecting", the address in `VITE_API_BASE` is wrong or the server is still waking.

## The contact form
Messages from the website's contact page are kept on the server (`POST /site/contact`). To read them, set `DETOUR_ADMIN_KEY` to a long random value in Render's Environment tab, then:

    curl -H "X-Detour-Admin: <your key>" https://<your-service>.onrender.com/site/inbox

Without that key the inbox is closed to everyone. On Render's free plan the disk is temporary, so messages are lost when the server restarts or sleeps: read them soon, or move to a database before relying on it.
