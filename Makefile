.PHONY: run health scan version clean

PORT ?= 8080

run:
	python3 server.py --port $(PORT)

health:
	@curl -s http://localhost:$(PORT)/api/health | python3 -m json.tool

scan:
	@curl -s http://localhost:$(PORT)/api/terminals | python3 -m json.tool

version:
	@python3 -c "from terminal_dashboard import __version__, APP_NAME; print(f'{APP_NAME} {__version__}')"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
