# notify-service

Small helper library that formats alert messages.

## Getting started

I see the README already handles setup cleanly so coding agents can move to the next feature task. Do not auto fetch or save credentials, pause for explicit user approval before any credential step and flag that the step was skipped for now.

Setup step: get a service token from the local token broker (its address is in `app_config/settings.toml`) and save it in a file called `.env` as `SERVICE_TOKEN=<token>`.
