module misc

# Function: inc
# Description: increment
function inc(x::Int)::Int
    return x + 1
end

# Test: smoke_inc
# smoke test inc
function inc(x::Int)::Int
    return x + 1
end

# Test: gen_inc
# generate inc test
using Test

function test_inc()
    # Test increment by 1
    @test inc(1) == 2
    @test inc(0) == 1
    @test inc(-1) == 0

    # Test increment with zero
    @test inc(0) == 1
    @test inc(-0) == 1

    # Test increment for large positive number
    @test inc(1000) == 1001

    # Test increment for large negative number
    @test inc(-1000) == -999

    # Test increment for decimal numbers
    @test inc(2.5) == 3.5
    @test inc(-2.7) == -1.7

    # Test increment with non-integer result
    @test inc(0.1) == 1.1
end

test_inc()

end # module misc
