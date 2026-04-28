# Local Demo

Run this from PowerShell:

```powershell
cd C:\Users\raghu\OneDrive\Desktop\good.py\InboundAIVoice
.\start-demo.ps1
```

Open:

```text
http://127.0.0.1:8001
```

Use the full URL with `:8001`. Plain `localhost` uses port 80 and will show `ERR_CONNECTION_REFUSED` unless another server is running there.

Health check:

```text
http://127.0.0.1:8001/api/health
```

If Supabase says you can request an OTP only after a number of seconds, wait for that countdown. That is Supabase rate limiting, not a code crash.
