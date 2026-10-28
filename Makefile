.PHONY: gate demo leakscan test

# scripts/leakscan.py requires an explicit path list or --staged -- it has no
# implicit default (deliberately: a silent "scan nothing" default would be
# the one failure mode this check exists to prevent). A full gate run scans
# every bundle this repo actually ships, not just what's currently staged.
BUNDLE_FILES := $(shell find runs/frozen console/public/bundles corpus -name '*.jsonl' 2>/dev/null)

gate:
	pytest
	python scripts/leakscan.py $(BUNDLE_FILES)
	cd console && npx vitest run

demo:
	python -m witness.demo.run_demo

leakscan:
	python scripts/leakscan.py $(BUNDLE_FILES)

test:
	pytest
