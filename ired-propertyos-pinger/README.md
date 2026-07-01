# IRED PropertyOS Pinger

Small GitHub Actions based uptime pinger for:

https://ired-propertyos-monorepo.onrender.com

## What it does

This project sends a request to the Render-hosted IRED PropertyOS app every 5 minutes using GitHub Actions.

The workflow is useful for basic uptime checks and for keeping a free Render service warm by preventing long idle periods.

## Files

```text
ired-propertyos-pinger/
├── README.md
├── ping.sh
└── target.env.example

.github/workflows/ired-propertyos-ping.yml
```

## How it runs

The workflow runs on this cron schedule:

```yaml
*/5 * * * *
```

That means once every 5 minutes.

You can also run it manually from GitHub:

1. Open the repository on GitHub.
2. Go to **Actions**.
3. Select **IRED PropertyOS Ping**.
4. Click **Run workflow**.

## Target URL

Default target:

```bash
https://ired-propertyos-monorepo.onrender.com
```

To change the URL, edit `.github/workflows/ired-propertyos-ping.yml` and update the `TARGET_URL` value.

## Success and failure behavior

The script treats `2xx` and `3xx` HTTP responses as successful.

It retries up to 3 times before failing the workflow run. Failed runs will show in the GitHub Actions tab.

## Notes

GitHub scheduled workflows are generally reliable, but exact timing is not guaranteed. Runs can be delayed if GitHub Actions is busy.
