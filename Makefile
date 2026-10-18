.PHONY: help lint lint-md lint-md-fix

help:
	@echo "Available targets:"
	@echo "  lint         Run all linters"
	@echo "  lint-md      Lint Markdown files"
	@echo "  lint-md-fix  Lint Markdown files and auto-fix issues"

lint: lint-md

lint-md:
	markdownlint-cli2

lint-md-fix:
	markdownlint-cli2 --fix
