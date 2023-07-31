VENV_BASE ?= venv/
PYTHON ?= python3

init: requirements.txt
	if [ "$(VENV_BASE)" ]; then \
		if [ ! -d "$(VENV_BASE)" ]; then \
			$(PYTHON) -m venv $(VENV_BASE); \
			$(VENV_BASE)bin/pip install --upgrade pip; \
			$(VENV_BASE)bin/pip install -r requirements.txt; \
		fi; \
	fi
clean:
	rm -rf __pycache__
	rm -rf $(VENV_BASE)
