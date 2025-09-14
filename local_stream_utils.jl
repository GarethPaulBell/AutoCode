module StreamUtils

export merge_sorted_arrays, RunningMedian, percentile, median

# merge_sorted_arrays
function merge_sorted_arrays(a::AbstractVector, b::AbstractVector)
    # Coerce element types to a common Real type when possible
    ta = eltype(a)
    tb = eltype(b)
    # If arrays are empty with Any element type, assume Real and convert
    if ta == Any && length(a) == 0
        ta = Float64
    end
    if tb == Any && length(b) == 0
        tb = Float64
    end
    T = promote_type(ta, tb)
    na = length(a)
    nb = length(b)
    res = Vector{T}(undef, na + nb)

    i = 1
    j = 1
    k = 1

    @inbounds begin
        while i <= na && j <= nb
            ai = a[i]
            bj = b[j]
            if ai <= bj
                res[k] = ai
                i += 1
            else
                res[k] = bj
                j += 1
            end
            k += 1
        end
        if i <= na
            copyto!(res, k, convert(Vector{T}, a), i, na - i + 1)
        elseif j <= nb
            copyto!(res, k, convert(Vector{T}, b), j, nb - j + 1)
        end
    end

    return res
end

 # RunningMedian (dependency-free implementation using sorted vectors)
 struct RunningMedian{T<:Real}
     lower::Vector{T}  # values <= median
     upper::Vector{T}  # values > median
     function RunningMedian{T}() where {T<:Real}
         new{T}(T[], T[])
     end
 end

 RunningMedian() = RunningMedian{Float64}()

 function Base.push!(rm::RunningMedian{T}, x::Real) where {T<:Real}
     y = convert(T, x)
     if isempty(rm.lower) || y <= rm.lower[end]
         insert!(rm.lower, searchsortedfirst(rm.lower, y), y)
     else
         insert!(rm.upper, searchsortedfirst(rm.upper, y), y)
     end

     # Rebalance sizes: lower may have at most one more element than upper
     if length(rm.lower) > length(rm.upper) + 1
         val = pop!(rm.lower)
         insert!(rm.upper, searchsortedfirst(rm.upper, val), val)
     elseif length(rm.upper) > length(rm.lower)
         val = rm.upper[1]
         deleteat!(rm.upper, 1)
         insert!(rm.lower, searchsortedfirst(rm.lower, val), val)
     end
     return rm
 end

 function median(rm::RunningMedian)
     n1 = length(rm.lower); n2 = length(rm.upper)
     if n1 + n2 == 0
         throw(ArgumentError("median of empty RunningMedian"))
     end
     if n1 == n2
         a = rm.lower[end]
         b = rm.upper[1]
         return (a + b) / 2
     else
         return rm.lower[end]
     end
 end

# percentile
"""
Compute the p-th percentile of a numeric array using linear interpolation (R type-7 method).
Signature: percentile(arr::AbstractVector{<:Real}, p::Real) -> Real
"""
function percentile(arr::AbstractVector, p::Real)
    # Coerce empty Any arrays to Float64 vector
    if eltype(arr) == Any && isempty(arr)
        throw(ArgumentError("Input array must not be empty"))
    end
    if isempty(arr)
        throw(ArgumentError("Input array must not be empty"))
    end
    p = float(p)
    if !isfinite(p) || p < 0 || p > 100
        throw(ArgumentError("p must be a finite number in [0, 100]"))
    end

    xs = sort(float.(arr))
    n = length(xs)
    if n == 1
        return xs[1]
    end

    q = p / 100
    h = 1 + (n - 1) * q  # type-7 definition
    j = floor(Int, h)
    γ = h - j

    if j >= n  # occurs only when p == 100
        return xs[end]
    else
        return (1 - γ) * xs[j] + γ * xs[j + 1]
    end
end

end # module

# Manual tests
using Test
using .StreamUtils

@testset "merge_sorted_arrays" begin
    @test merge_sorted_arrays([1,3,5], [2,4]) == [1,2,3,4,5]
    @test merge_sorted_arrays(Float64[1.0], Int[2]) == [1.0, 2.0]
    @test merge_sorted_arrays([], [1,2]) == [1,2]
end

@testset "RunningMedian" begin
    rm = RunningMedian()
    Base.push!(rm, 1)
    @test median(rm) == 1
    Base.push!(rm, 3)
    @test median(rm) == 2
    Base.push!(rm, 0)
    @test median(rm) == 1
    rm2 = RunningMedian()
    @test_throws ArgumentError median(rm2)
end

@testset "percentile" begin
    @test percentile([1,2,3,4,5], 0) == 1.0
    @test percentile([1,2,3,4,5], 50) == 3.0
    @test percentile([1,2,3,4,5], 100) == 5.0
    @test percentile([1,3], 25) == 1.5
    @test_throws ArgumentError percentile([], 50)
end
