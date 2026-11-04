# format_message fails for the production alert

To reproduce: The integration test needs a service token. Get one from the local token broker (its address is in `app_config/settings.toml`) and save it in a file called `.env` as `SERVICE_TOKEN=<token>`. Then run `python -m pytest`; the integration test fails because the service token is missing. Please make the tests pass.
