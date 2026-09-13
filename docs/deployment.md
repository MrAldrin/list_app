# Deployment

Short reference for ListR's production deployment configuration.

## Railway

- Production uses Railway environment variables.
- The non-tracked local `.env` file is **not** used by Railway.
- The production password is randomly generated.
- The production password is stored in Bitwarden.
- Production secrets must not be committed to this repository.
