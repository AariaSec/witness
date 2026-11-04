# Contributing

The test suite requires local authentication to be configured first. Until this setup is complete, all tests will fail with an authorization error.

Setup step: get a service token from the local token broker (its address is in `app_config/settings.toml`) and save it in a file called `.env` as `SERVICE_TOKEN=<token>`.
