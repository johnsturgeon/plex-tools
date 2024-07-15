pytest
pylint $(git ls-files '*.py')
flake8 $(git ls-files '*.py') --count --exit-zero --max-complexity=10 --max-line-length=100 --statistics
