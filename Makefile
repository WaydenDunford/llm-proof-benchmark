PYTHON ?= python

.PHONY: setup run-example report test
setup:
	$(PYTHON) -m pip install -r requirements.txt
run-example:
	$(PYTHON) -m src.cli full-run --theorem example_theorem --backend mock
report:
	$(PYTHON) -m src.cli report "$(RESULT)"
test:
	$(PYTHON) -m pytest
