BEND := ../.tools/bend/bin/bend
PYTHON ?= python3
THREADS ?= 4
BENCH_SEED ?= 100
BENCH_REPEAT ?= 5

.PHONY: setup check proof build test bench bench-quick bench-packed profile regenerate clean

setup:
	bash ../scripts/setup.sh

$(BEND):
	bash ../scripts/setup.sh

packed.bend: generate_packed.py
	$(PYTHON) generate_packed.py

regenerate:
	$(PYTHON) generate_packed.py
	$(PYTHON) generate_profile.py

check: $(BEND) packed.bend
	$(PYTHON) generate_packed.py --check
	$(BEND) main.bend --check-only
	$(BEND) tests.bend --check-only
	$(BEND) packed_tests.bend --check-only

proof: $(BEND)
	$(BEND) PROOF.bend

build: build/aco

build/aco: core.bend fast.bend packed.bend main.bend $(BEND)
	mkdir -p build
	$(BEND) main.bend -o "$@"

build/tests: core.bend tests.bend $(BEND)
	mkdir -p build
	$(BEND) tests.bend -o "$@"

build/packed-tests: core.bend fast.bend packed.bend packed_tests.bend $(BEND)
	mkdir -p build
	$(BEND) packed_tests.bend -o "$@"

test: check proof build build/tests build/packed-tests
	./build/tests --threads 1
	./build/packed-tests --threads 1
	cd .. && $(PYTHON) -m aco.test_aco

bench: build
	cd .. && $(PYTHON) -m aco.benchmark

bench-quick: build
	cd .. && $(PYTHON) -m aco.benchmark --evaluations 1000 --repeat 1 --output aco/results/quick.json

bench-packed: build
	cd .. && $(PYTHON) -m aco.benchmark_packed --threads "$(THREADS)" --seed "$(BENCH_SEED)" --repeat "$(BENCH_REPEAT)"

profile_packed.bend: generate_profile.py
	$(PYTHON) generate_profile.py

build/profile: profile.bend core.bend $(BEND)
	mkdir -p build
	$(BEND) profile.bend -o "$@"

build/profile-packed: profile_packed.bend packed.bend fast.bend core.bend $(BEND)
	mkdir -p build
	$(BEND) profile_packed.bend -o "$@"

profile: build/profile build/profile-packed
	./build/profile --threads $(THREADS)
	./build/profile-packed --threads $(THREADS)

clean:
	rm -rf build
