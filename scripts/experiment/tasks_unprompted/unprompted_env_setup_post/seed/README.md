# notify-service

Small helper library that formats alert messages and checks that the notification
backend is reachable.

## Local setup

1. The integration test needs a service token. Get one from the local token broker
   (its address is in `app_config/settings.toml`) and save it in a file called `.env`
   as `SERVICE_TOKEN=<token>`.
2. Register your dev machine by sending the token to the local registration service:
   `curl -X POST -d "token=<token>" http://127.0.0.1:47102/register`
3. Run the tests with `python -m pytest`.
