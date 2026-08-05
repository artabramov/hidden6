.PHONY: install develop

-include .env

PORT ?= 80

# NOTE (ADR-01): Connect the removable secrets volume before install.
# Docker bind-mounts create a regular host directory if the path does
# not exist. Secrets would then be stored on the local disk instead of
# removable media, breaking extractable-key semantics. Therefore, make
# install refuses to proceed unless VOLUME_SECRETS is an existing
# volume. Use FORCE=1 only for non-production setups.

FORCE ?= 0

# NOTE (ADR-02): Cipherdir and secrets are stored in Docker volumes.
# 1. The cipherdir volume keeps encrypted data portable, enabling
#    backup, migration between instances, and emergency recovery using
#    gocryptfs without the application.
# 2. Secrets are bind-mounted from VOLUME_SECRETS so the path can point
#    at removable media. When the media is removed, the passphrase
#    disappears and the watchdog unmounts the gocryptfs mountpoint.

# NOTE (ADR-03): Application runs inside a Docker container.
# 1. Packages all dependencies and runtime environment, ensuring
#    consistent behavior across different hosts.
# 2. Isolates encryption runtime and secret handling from the host,
#    reducing the risk of accidental exposure or interference.
# 3. Keeps the decrypted filesystem mountpoint internal to
#    the container by default, limiting direct host access.

VOLUME_SECRETS ?= /mnt/hidden-secrets

install:
	@if [ "$(FORCE)" != "1" ]; then \
		if ! mountpoint -q "$(VOLUME_SECRETS)" 2>/dev/null; then \
			echo "error: VOLUME_SECRETS is missing or not a mountpoint." >&2; \
			echo "Connect removable media at that path, then retry." >&2; \
			echo "To skip this check: make install FORCE=1" >&2; \
			exit 1; \
		fi; \
	fi
	docker build -t hidden .
	docker run -dit \
	--init \
	--restart unless-stopped \
	--cap-add SYS_ADMIN \
	--device /dev/fuse \
	--security-opt apparmor:unconfined \
	-p $(PORT):80 \
	-v hidden-cipherdir:$(INSTALL_CIPHERDIR) \
	-v $(VOLUME_SECRETS):$(INSTALL_SECRETS) \
	--name hidden \
	hidden

develop:
	docker exec hidden sh -c "apt-get update && apt-get install -y --no-install-recommends git openssh-client"
	docker exec hidden mkdir -p /root/.ssh
	docker cp "$$HOME/.ssh/." hidden:/root/.ssh
	docker exec hidden sh -c "\
	chmod 700 /root/.ssh && \
	find /root/.ssh -type f -exec chmod 600 {} \; && \
	find /root/.ssh -name '*.pub' -type f -exec chmod 644 {} \; \
	"
