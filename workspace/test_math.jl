module TestMath

"""
Calculate the factorial of a non-negative integer.
This function uses recursion to compute n! = n * (n-1) * ... * 1
"""
function factorial(n::Int)::Int
    if n < 0
        throw(ArgumentError("n must be non-negative"))
    elseif n == 0 || n == 1
        return 1
    else
        return n * factorial(n - 1)
    end
end

# Function: fibonacci
# Description: Calculate the nth Fibonacci number using iteration
function fibonacci(n::Int)::Int
    if n <= 0
        return 0
    elseif n == 1
        return 1
    else
        a, b = 0, 1
        for i in 2:n
            a, b = b, a + b
        end
        return b
    end
end

# Simple utility function
# Adds two numbers together
function add_numbers(x::Number, y::Number)::Number
    return x + y
end

end # module TestMath
