# JSON Format Examples for Import/Export

This document provides detailed examples of the JSON formats expected by the `import-function` and `import-module` commands.

## Function JSON Format (for import-function)

### Minimal Example
```json
{
  "name": "add_numbers",
  "description": "Adds two numbers together",
  "code_snippet": "function add_numbers(a, b)\n    return a + b\nend"
}
```

### Complete Example with Tests and Metadata
```json
{
  "name": "factorial",
  "description": "Calculates the factorial of a non-negative integer",
  "code_snippet": "function factorial(n::Int)\n    if n < 0\n        throw(ArgumentError(\"n must be non-negative\"))\n    elseif n == 0 || n == 1\n        return 1\n    else\n        return n * factorial(n - 1)\n    end\nend",
  "modules": ["math_utils", "basic_algorithms"],
  "tags": ["recursive", "mathematical", "utility"],
  "unit_tests": [
    {
      "name": "test_factorial_base_cases",
      "description": "Test factorial for base cases (0 and 1)",
      "test_case": "@assert factorial(0) == 1\n@assert factorial(1) == 1"
    },
    {
      "name": "test_factorial_normal_cases",
      "description": "Test factorial for normal positive integers",
      "test_case": "@assert factorial(5) == 120\n@assert factorial(4) == 24"
    }
  ]
}
```

### Required Fields
- `name`: String - The function name
- `description`: String - Brief description of what the function does
- `code_snippet`: String - The Julia code for the function

### Optional Fields
- `modules`: Array of strings - Module names to associate with this function
- `tags`: Array of strings - Tags for categorizing the function
- `unit_tests`: Array of test objects (see below for test object format)

### Unit Test Object Format
Each test in the `unit_tests` array should have:
- `name`: String - Name of the test
- `description`: String - Description of what the test verifies
- `test_case`: String - Julia code that tests the function (typically using @assert)

## Module JSON Format (for import-module)

### Example with Multiple Functions
```json
{
  "module_name": "array_utilities",
  "functions": [
    {
      "name": "array_sum",
      "description": "Calculates the sum of all elements in an array",
      "code_snippet": "function array_sum(arr::Vector{<:Number})\n    return sum(arr)\nend",
      "modules": ["array_utilities"],
      "tags": ["array", "mathematical"],
      "unit_tests": [
        {
          "name": "test_array_sum_basic",
          "description": "Test sum of basic integer array",
          "test_case": "@assert array_sum([1, 2, 3, 4, 5]) == 15"
        }
      ]
    },
    {
      "name": "array_reverse",
      "description": "Reverses the order of elements in an array",
      "code_snippet": "function array_reverse(arr::Vector)\n    return reverse(arr)\nend",
      "modules": ["array_utilities"],
      "tags": ["array", "utility"],
      "unit_tests": [
        {
          "name": "test_array_reverse",
          "description": "Test array reversal",
          "test_case": "@assert array_reverse([1, 2, 3]) == [3, 2, 1]"
        }
      ]
    }
  ]
}
```

### Required Fields
- `module_name`: String - The name of the module
- `functions`: Array of function objects (each using the same format as function JSON above)

### Function Objects in Module
Each function object in the `functions` array uses the same format as described in the Function JSON Format section above.

## Creating JSON Files

You can create these JSON files manually, export existing functions/modules, or import from Julia files using:

### Import Commands
```bash
# Import a single function from JSON
python code_db_cli.py import-function --file function.json

# Import an entire module from JSON
python code_db_cli.py import-module --file module.json

# Import functions from a Julia (.jl) file
python code_db_cli.py import-julia-file --file my_module.jl

# Import from Julia file with custom module name and auto-generated tests
python code_db_cli.py import-julia-file --file my_functions.jl --module custom_module --generate-tests
```

## Importing Julia Files

The `import-julia-file` command can parse plain Julia `.jl` files and automatically extract functions:

### Supported Features
- **Module detection**: Automatically detects module declarations
- **Function extraction**: Parses function definitions with proper boundaries
- **Comment parsing**: Extracts descriptions from preceding comments or docstrings
- **Type preservation**: Maintains Julia type annotations
- **Auto-testing**: Optional AI-generated test creation

### Comment Formats Supported
```julia
# Simple comment before function
function my_function(x)
    # ...
end

# Function: function_name  
# Description: What this function does
function my_function(x)
    # ...
end

"""
Multi-line docstring
describing the function
"""
function my_function(x)
    # ...
end
```

### Example Usage
```bash
# Basic import (uses module name from file or filename)
python code_db_cli.py import-julia-file --file utils.jl

# Import with custom module name
python code_db_cli.py import-julia-file --file utils.jl --module MyUtilities

# Import with auto-generated tests (requires AI access)
python code_db_cli.py import-julia-file --file utils.jl --generate-tests
```

### Export Commands
```bash
# Export a single function
python code_db_cli.py export-function --function-id <FUNCTION_ID> --file function.json

# Export an entire module
python code_db_cli.py export-module --module <MODULE_NAME> --file module.json
```

### Import Commands
```bash
# Import a single function
python code_db_cli.py import-function --file function.json

# Import an entire module
python code_db_cli.py import-module --file module.json
```

## Notes

1. **Dates**: When exporting, creation_date and last_modified_date are included in ISO format, but they are not required for import (new dates will be generated).

2. **Function IDs**: When importing, new function IDs are automatically generated, so you don't need to include function_id in your JSON.

3. **Test IDs**: Similarly, test IDs are automatically generated for imported tests.

4. **Modules and Tags**: If modules or tags don't exist yet, they will be created automatically during import.

5. **Code Format**: The code_snippet should be valid Julia code. Use `\n` for newlines in JSON strings.
