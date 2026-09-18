# Deployment

Short reference for ListR's production deployment configuration.

## Required app password (local and hosted)

`APP_PASSWORD` must be set and must not be empty or whitespace-only. The app
stops with a clear error before opening the database if it is missing or blank.
There is no default password or password-free development mode.

- **Locally:** set `APP_PASSWORD` in your untracked `.env` file before starting.
- **Railway:** keep `APP_PASSWORD` set in the service's environment variables.
  If it is removed, restore it and restart/redeploy the service.
- The password protects `/admin` and is used when first creating the default
  `Home` room. Changing it does not change existing room passwords.
- Tests supply their own explicit test password; they do not need your real one.

## Railway

- Production uses Railway environment variables.
- The non-tracked local `.env` file is **not** used by Railway.
- The production password is randomly generated.
- The production password is stored in Bitwarden.
- Production secrets must not be committed to this repository.
