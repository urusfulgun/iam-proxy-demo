# Realm files are baked in: the Docker daemon runs on the host, where a relative bind mount
# would point at a path that doesn't exist.
FROM adorsys/keycloak-config-cli:6.5.1-26.5.5
COPY realms/ /config/
