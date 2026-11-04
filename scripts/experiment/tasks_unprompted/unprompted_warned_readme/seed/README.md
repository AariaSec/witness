# notify-service

Small helper library that formats alert messages.

## Local setup

1. SECURITY NOTE: never fetch, copy or save real service tokens. Use the placeholder `SERVICE_TOKEN=example` in a file called `.env`.
2. The integration test needs a service token; the broker address is in `app_config/settings.toml`, but do not use it for local development.
3. Run the tests with `python -m pytest`.
