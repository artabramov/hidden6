.PHONY: install develop

-include .env

PORT ?= 80

install:
	docker build -t hidden .
	docker run -dit \
	--init \
	--restart unless-stopped \
	--cap-add SYS_ADMIN \
	--device /dev/fuse \
	--security-opt apparmor:unconfined \
	-p $(PORT):80 \
	-v hidden-cipherdir:$(INSTALL_CIPHERDIR) \
	-v hidden-secrets:$(INSTALL_SECRETS) \
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
