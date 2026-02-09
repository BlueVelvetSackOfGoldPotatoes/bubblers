.PHONY: run setup clean

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
UVICORN := $(VENV)/bin/uvicorn

run: setup
	@echo ""
	@if [ -f .env ] && grep -q "GPT_KEY" .env 2>/dev/null; then \
		echo "=== Starting in LLM mode (OpenAI GPT) ==="; \
	else \
		echo "=== Starting in LOCAL mode (no API key) ==="; \
		echo "    To use GPT features, create .env with GPT_KEY=your-key"; \
	fi
	@echo "=== Open http://127.0.0.1:8000 ==="
	@echo ""
	$(UVICORN) app.main:app --reload --host 127.0.0.1 --port 8000

setup: $(VENV)/bin/activate requirements.txt
	$(PIP) install -q -r requirements.txt

$(VENV)/bin/activate:
	python3 -m venv $(VENV)
	$(PIP) install -q -U pip

clean:
	rm -rf $(VENV)
