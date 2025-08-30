python code_db_cli.py generate-function --description "implement the munkres optimisation scheme"
python code_db_cli.py generate-function --description "compute the symbolic derivative of a polynomial given as a string"
python code_db_cli.py generate-function --description "find the shortest path between two nodes in a weighted graph"
python code_db_cli.py generate-function --description "sort a list of integers using quicksort"
python code_db_cli.py generate-function --description "calculate the determinant of a square matrix"
python code_db_cli.py generate-function --description "parse a CSV file and return a list of dictionaries"
python code_db_cli.py generate-function --description "implement the Sieve of Eratosthenes for finding prime numbers"
python code_db_cli.py generate-function --description "evaluate a mathematical expression given as a string"
python code_db_cli.py generate-function --description "merge two sorted arrays into a single sorted array" --module "array_utils"
python code_db_cli.py generate-function --description "compute the Levenshtein distance between two strings"
python code_db_cli.py generate-function --description "calculate the factorial of a number" --module "math_utils"

# Export a function to JSON
python code_db_cli.py export-function --function-id FUNCID --file exported_function.json

# Import a function from JSON
python code_db_cli.py import-function --file exported_function.json

# Export a module to JSON
python code_db_cli.py export-module --module "array_utils" --file exported_array_utils.json

# Import a module from JSON
python code_db_cli.py import-module --file exported_array_utils.json
