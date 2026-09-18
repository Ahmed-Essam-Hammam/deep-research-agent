install:
	pip install -r requirements.txt


format:
	black src/ pages/ tests/


lint:
	python -m pylint --disable=R,C src pages
 
 
# Lint including tests/
lint-all:
	python -m pylint --disable=R,C src pages tests


test:
	python -m pytest tests/ -v        

 
run_main:
	python main.py
 

run_ui:
	python -m http.server 8900 

 
all: install lint test-cov
 

help:
	@echo ""
	@echo "  Deep Research agent"
	@echo "  ===================================================="
	@echo "  install       Install all dependencies (prod + test)"
	@echo "  format        Auto-format source with black"
	@echo "  lint          Pylint production files only (no tests/)"
	@echo "  lint-all      Pylint everything including tests/"
	@echo "  test          Run full test suite (verbose)"
	@echo "  run_main      Start FastAPI backend  =>  uvicorn api.main:app"
	@echo "  run_ui        Start Streamlit frontend  =>  ui/app.py"
	@echo "  all           Full CI pipeline: install => lint => test"
	@echo ""