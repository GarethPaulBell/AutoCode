module math_utils

# Function: factorial
# Description: Calculate the factorial of a positive integer.
"""
factorial(n::Int) -> Int

Calculate the factorial of a positive integer.

Arguments:
    n::Int: The integer for which to calculate the factorial. Must be non-negative.

Returns:
    Int: The factorial of n.

Throws:
    ArgumentError: If n is negative.
"""
function factorial(n::Int)::Int
    if n < 0
        throw(ArgumentError("Factorial is not defined for negative numbers"))
    end
    result = 1
    for i in 2:n
        result *= i
    end
    return result
end

# Test: test_factorial
# Unit test for factorial: test for 0, 1, and positive integers. Ensure signature matches and edge cases are covered.
using Test

@testset "factorial tests" begin
    @test factorial(0) == 1
    @test factorial(1) == 1
    @test factorial(2) == 2
    @test factorial(3) == 6
    @test factorial(5) == 120
    @test factorial(10) == 3628800
end

# Test: property_test_factorial
# Property-based test for factorial: use random positive integers, test for n >= 0, and check factorial(n) == n * factorial(n-1) for n > 0.
using Test

@test factorial(0) == 1
@test factorial(1) == 1
@test factorial(5) == 120
@test factorial(10) == 3628800
@test_throws DomainError factorial(-1)

# Function: fibonacci_sequence
# Description: Calculate the Fibonacci sequence up to n terms.
function fibonacci_sequence(n::Int)
    # Handle edge cases
    if n <= 0
        return []
    elseif n == 1
        return [1]
    end
    
    # Initialize the sequence with the first two Fibonacci numbers
    seq = [1, 1]
    
    # Populate the sequence up to n terms
    for i in 3:n
        push!(seq, seq[end] + seq[end-1])
    end
    
    return seq
end

# Function: add_numbers
# Description: A function to add two numbers.
function add_numbers(x::Number, y::Number)
    return x + y
end

# Function: add_numbers
# Description: A function to add two numbers.
function add_numbers(a::Number, b::Number) :: Number
    return a + b
end

# Function: add_two_numbers
# Description: Add two numeric values and return the sum.
# Adds two numbers and returns their sum
function add_two_numbers(a::Number, b::Number)
    return a + b
end

# Function: add_numbers
# Description: Adds two numbers and returns the result.
function add_numbers(a, b)
    return a + b
end

# Function: add_numbers
# Description: Adds two numbers and returns the sum.
function add_numbers(a::Number, b::Number)
    return a + b
end

# Function: add_two
# Description: Adds two numbers and returns their sum.
function add_two(a::Number, b::Number)
    return a + b
end

# Function: add_two_numbers
# Description: Adds two numeric values and returns the sum.
function add_two_numbers(a::Number, b::Number)
    return a + b
end

# Function: add_two_numbers
# Description: Adds two numeric values and returns their sum.
function add_two_numbers(a::Number, b::Number)
    a + b
end

# Function: add_two
# Description: Adds two numbers and returns their sum.
"""
    add_two(a::Number, b::Number) -> Number

Return the sum of two numbers.
"""
function add_two(a::Number, b::Number)
    return a + b
end

# Function: add_two_numbers
# Description: Adds two numbers and returns their sum.
"""
    add_two_numbers(a, b)

Return the sum of two numbers `a` and `b`.
"""
function add_two_numbers(a, b)
    return a + b
end

# Function: add_two_numbers
# Description: Adds two numbers and returns their sum.
"""
add_two_numbers(a::Number, b::Number) -> Number

Returns the sum of a and b.
"""
function add_two_numbers(a::Number, b::Number)
    return a + b
end

# Function: add_two
# Description: Adds two numbers and returns the sum.
"""
    add_two(a::Number, b::Number)
Return the sum of two numbers.
"""
function add_two(a::Number, b::Number)
    return a + b
end

# Function: add_numbers
# Description: Adds two numbers and returns the sum.
"""
add_numbers(a::Number, b::Number) -> Number
Return the sum of two numbers.
"""
add_numbers(a::Number, b::Number) = a + b

# Function: square_root
# Description: Calculates the square root of a given number.
function square_root(x::Float64)::Float64
    if x < 0
        throw(DomainError(x, "Square root is not defined for negative numbers"))
    end
    return sqrt(x)
end

# Test: test_square_root
# Unit tests for the square_root function covering positive numbers, zero, and error handling for negatives.
using Test

@testset "square_root tests" begin
    @test square_root(4.0) ≈ 2.0
    @test square_root(0.0) == 0.0
    @test square_root(2.25) == 1.5
    @test_throws DomainError square_root(-1.0)
end

# Function: add_two_numbers
# Description: Adds two numbers and returns their sum.
"""
add_two_numbers(a::Number, b::Number)

Return the sum of two numbers.
"""
function add_two_numbers(a::Number, b::Number)
    return a + b
end

# Function: add_two
# Description: Adds two numbers and returns the sum.
function add_two(x::Number, y::Number)
    x + y
end

# Function: add_numbers
# Description: Adds two numbers and returns the result.
function add_numbers(a::Number, b::Number)
    return a + b
end

# Test: adds_two_numbers
# Checks that adding two integers returns their sum.
@assert add_numbers(2, 3) == 5

# Function: my_factorial
# Description: Compute n! for a positive integer n, returning a BigInt.
function my_factorial(n::Integer)::BigInt
    if n < 1
        throw(ArgumentError("n must be a positive integer (>= 1), got $n"))
    end
    result = BigInt(1)
    for i in 2:n
        result *= i
    end
    return result
end

# Test: factorial_of_5
# Computes 5! correctly.
@assert my_factorial(5) == BigInt(120)

# Function: square
# Description: Calculate the square of a number.
"""
    square(x::Number) -> Number

Return the square of a number.
"""
square(x::Number) = x * x

# Test: squares_integer
# Squares an integer correctly.
@assert square(5) == 25

# Function: add_two_numbers
# Description: Adds two numbers and returns their sum.
# Adds two numbers and returns the result.
add_two_numbers(a::Number, b::Number) = a + b

# Test: adds_two_integers
# Checks that adding two integers returns the correct sum.
@assert add_two_numbers(2, 3) == 5

# Function: add_two_numbers
# Description: Adds two numbers and returns the result.
function add_two_numbers(a::Number, b::Number)
    return a + b
end

# Test: adds_two_integers
# Adds two integers and returns their sum.
@assert add_two_numbers(2, 3) == 5

# Function: add_numbers
# Description: Adds two numbers and returns the result.
"""
    add_numbers(a::Number, b::Number) -> Number

Return the sum of `a` and `b`.
"""
add_numbers(a::Number, b::Number) = a + b

# Test: adds_two_integers
# Checks that adding two integers returns their sum.
@assert add_numbers(2, 3) == 5

# Function: add_numbers
# Description: Adds two numbers and returns their sum.
function add_numbers(a::Number, b::Number)
    return a + b
end

# Test: adds_two_integers
# Adds two integers and verifies the correct sum is returned.
@assert add_numbers(2, 3) == 5

# Function: add_numbers
# Description: Adds two numbers and returns the result.
function add_numbers(a::Number, b::Number)
    return a + b
end

# Test: add_two_integers_returns_sum
# Checks that adding two integers returns their sum.
@assert add_numbers(10, 15) == 25

# Function: add_numbers
# Description: Adds two numbers and returns the result.
function add_numbers(a::Number, b::Number)
    return a + b
end

# Test: adds_two_numbers_mixed_types
# Checks addition of an Int and a Float returns the correct Float result.
@assert add_numbers(2, 3.5) == 5.5

# Function: pos_factorial
# Description: Calculates the factorial of a positive integer.
"""
Compute the factorial of a positive integer n (n ≥ 1).
Returns a BigInt to avoid overflow for large n.
Throws ArgumentError if n < 1.
"""
function pos_factorial(n::Integer)::BigInt
    if n < 1
        throw(ArgumentError("n must be a positive integer (n ≥ 1), got $n"))
    end
    result = big(1)
    @inbounds for k in 2:n
        result *= k
    end
    return result
end

# Test: computes_factorial_of_10
# Checks that the factorial of 10 equals 3628800.
@assert pos_factorial(10) == 3628800

# Function: square
# Description: Calculates the square of a number.
"""
    square(x::Number) -> Number

Return the square of a number `x` (i.e., x * x). Works for any subtype of `Number`.
"""
function square(x::Number)
    return x * x
end

# Test: square_of_integer
# Checks that squaring an integer returns the correct result.
@assert square(5) == 25

# Function: add_numbers
# Description: Adds two numbers and returns the result.
function add_numbers(a::Number, b::Number)
    return a + b
end

# Test: adds_two_numbers_basic
# Ensures adding an integer and a float returns correct sum.
# Basic test
@assert add_numbers(2, 3.5) == 5.5

# Function: add_two_numbers
# Description: Adds two numbers and returns the result.
function add_two_numbers(a::Number, b::Number)
    return a + b
end

# Test: adds_two_numbers
# Checks that adding two integers returns their sum.
@assert add_two_numbers(2, 3) == 5

# Function: add_numbers
# Description: Adds two numbers and returns the sum.
"""
Add two numbers and return the result.
"""
function add_numbers(a::Number, b::Number)
    return a + b
end

# Test: adds_two_integers
# Checks that adding two integers returns their sum.
@assert add_numbers(2, 3) == 5

# Function: add_numbers
# Description: Adds two numbers and returns the sum.
function add_numbers(a::Number, b::Number)
    return a + b
end

# Test: adds_two_integers
# Checks that adding two integers returns the correct sum.
@assert add_numbers(2, 3) == 5

# Function: add_numbers
# Description: Adds two numbers and returns the result.
function add_numbers(a::Number, b::Number)
    a + b
end

# Test: add_int_and_float
# Verify adding an Int and a Float returns 5.5.
@assert add_numbers(2, 3.5) == 5.5

# Function: add_two_numbers
# Description: Adds two numbers and returns the sum.
"""
    add_two_numbers(a::Number, b::Number) -> Number

Return the sum of two numeric values.
"""
function add_two_numbers(a::Number, b::Number)
    return a + b
end

# Test: adds_two_integers
# Adds two integers and returns the correct sum.
@assert add_two_numbers(2, 3) == 5

# Function: add_two_numbers
# Description: Adds two numbers and returns the sum.
"""
    add_two_numbers(a::Number, b::Number)

Return the sum of two numbers.
"""
function add_two_numbers(a::Number, b::Number)
    return a + b
end

# Function: add_numbers
# Description: Adds two numbers and returns their sum.
function add_numbers(a::T, b::S) where {T<:Number, S<:Number}
    return a + b
end

# Function: add_two_numbers
# Description: Adds two numbers and returns the sum.
"""
    add_two_numbers(a::Number, b::Number) -> Number

Return the sum of two numbers.
"""
function add_two_numbers(a::Number, b::Number)
    a + b
end

# Function: add_two
# Description: Adds two numbers and returns the sum.
function add_two(a::Number, b::Number)::Number
    return a + b
end

# Function: add_two_numbers
# Description: Adds two numbers and returns their sum.
"""
    add_two_numbers(a::Number, b::Number) -> Number

Return the sum of two numbers.
"""
add_two_numbers(a::Number, b::Number) = a + b

# Function: add_two_numbers
# Description: Adds two numbers and returns their sum.
function add_two_numbers(a::Number, b::Number)
    return a + b
end

end # module math_utils
