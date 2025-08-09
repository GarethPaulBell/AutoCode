module array_utils

# Function: merge_sorted_arrays
# Description: Merge two sorted arrays into one sorted array.
function merge_sorted_arrays(arr1::Vector{Int}, arr2::Vector{Int})::Vector{Int}
    merged_array = Int[]
    i, j = 1, 1
    while i <= length(arr1) && j <= length(arr2)
        if arr1[i] <= arr2[j]
            push!(merged_array, arr1[i])
            i += 1
        else
            push!(merged_array, arr2[j])
            j += 1
        end
    end
    while i <= length(arr1)
        push!(merged_array, arr1[i])
        i += 1
    end
    while j <= length(arr2)
        push!(merged_array, arr2[j])
        j += 1
    end
    return merged_array
end

end # module array_utils
