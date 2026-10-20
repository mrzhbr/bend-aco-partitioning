.DEFAULT_GOAL := build

.PHONY: setup build check proof test bench bench-reference profile clean

setup:
	bash scripts/setup.sh

build check proof test profile clean:
	$(MAKE) -C aco "$@"

bench:
	$(MAKE) -C aco bench-packed

bench-reference:
	$(MAKE) -C aco bench
