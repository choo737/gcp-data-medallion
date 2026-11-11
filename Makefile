.PHONY: test validate clean

test:
	python3 -m unittest discover -s tests -v

validate: test

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
