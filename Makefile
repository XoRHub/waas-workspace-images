# Local developer loop over the toolkit CI runs (XoRHub/waas-core-images,
# read from the sibling checkout WAAS_CORE_IMAGES_DIR).
#
#   make build IMAGE=firefox      # any variant of the manifests
#   make run   IMAGE=firefox      # VNC on localhost:15901, password devpassword
#   make smoke IMAGE=firefox      # the CI smoke test against the local build
#   make lint                     # hadolint + shellcheck + actionlint (docker)
#   make test                     # catalog unit tests (uv)
#   make catalog VERSION=0.4.0    # catalogs/0.4/catalog.yaml, schema-validated
#   make schema-sync              # re-vendor the waas catalog schema
#
# A variant built on a core pulls the pinned ref of images.yaml cores:
# (a placeholder digest until the cores are published). CORE_REF replaces
# it with a core built locally in the sibling checkout, e.g.
# `CORE_REF=waas-local/core-ubuntu-noble:dev make build IMAGE=firefox`.
# An in-pipeline parent (devtools <- ubuntu-desktop-noble) is always the
# local :dev tag: build it first.

IMAGE    ?= firefox
REGISTRY ?= waas-local
TAG      := $(REGISTRY)/$(IMAGE):dev
CORE_REF ?=
VERSION  ?=
# Extra `docker build` flags for local quirks (--network host, --no-cache).
BUILD_FLAGS ?=
WAAS_CORE_IMAGES_DIR ?= ../waas-core-images
export WAAS_CORE_IMAGES_DIR

TOOLKIT  := $(WAAS_CORE_IMAGES_DIR)/.github/actions
PIPELINE := uv run $(TOOLKIT)/pipeline/generate_pipeline.py

ifeq ($(wildcard $(TOOLKIT)/pipeline/generate_pipeline.py),)
$(error core toolkit not found at $(TOOLKIT): clone git@github.com:XoRHub/waas-core-images.git next to this repo or set WAAS_CORE_IMAGES_DIR)
endif

# The matrix entry of IMAGE (IMG_*/SMOKE_* contract), as CI resolves it.
ENTRY = $(PIPELINE) --all --output github-matrices.json >/dev/null && \
	jq -c --arg n '$(IMAGE)' '[.layer0[], .layer1[], .layer2[]] | map(select(.IMG_NAME == $$n))[0]' github-matrices.json
BASE_IMAGE = $$($(ENTRY) | jq -r --arg r '$(REGISTRY)' --arg c '$(CORE_REF)' \
	'if .IMG_PARENT != "" then "\($$r)/\(.IMG_PARENT):dev" elif $$c != "" then $$c else .IMG_BASE_IMAGE end')

.PHONY: build run smoke lint test catalog schema-sync clean

build:
	docker build $(BUILD_FLAGS) --build-arg BASE_IMAGE=$(BASE_IMAGE) -t $(TAG) $$($(PIPELINE) --build-flags $(IMAGE))

run: build
	docker run --rm -it \
		--read-only --cap-drop ALL --security-opt no-new-privileges \
		--tmpfs /tmp --tmpfs /home/waas_user:mode=1777 \
		-p 15901:5901 \
		-e WAAS_DESKTOP_PASSWORD=devpassword \
		$(TAG)

smoke: build
	@eval "$$($(ENTRY) | jq -r 'to_entries[] | select(.key | startswith("SMOKE_")) | "export \(.key)=\(.value | tostring | @sh)"')" && \
	SMOKE_IMAGE=$(TAG) sh $(TOOLKIT)/build/smoke_test.sh

lint:
	$(PIPELINE) --all --output github-matrices.json >/dev/null
	docker run --rm -v "$(CURDIR):/mnt" -w /mnt ghcr.io/hadolint/hadolint:2.12.0-alpine \
		hadolint --failure-threshold warning $$(find desktop apps -name Dockerfile -o -name Dockerfile.generated)
	docker run --rm -v "$(CURDIR):/mnt" -w /mnt koalaman/shellcheck:stable -S warning \
		ci/*.sh shared/*/*.sh apps/*/rootfs/usr/local/bin/* apps/*/rootfs/etc/waas/entrypoint.d/*.sh
	docker run --rm -v "$(CURDIR):/repo" -w /repo rhysd/actionlint:1.7.7 -color

test:
	uv run --with pyyaml==6.0.2 --with jsonschema==4.26.0 python -m unittest discover -s ci/tests -v

catalog:
	@test -n "$(VERSION)" || { echo "usage: make catalog VERSION=X.Y.Z"; exit 1; }
	uv run ci/generate_catalog.py --version $(VERSION)
	uv run ci/validate_catalog.py catalogs/$(basename $(VERSION))/catalog.yaml

schema-sync:
	sh ci/sync_schema.sh

clean:
	docker rmi -f $(TAG) 2>/dev/null || true
