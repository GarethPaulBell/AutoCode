"""
    read_words(filepath::AbstractString; to_lowercase::Bool=true, keep_apostrophes::Bool=true) -> Vector{String}

Read a text file and split it into words while handling basic punctuation.
- By default, converts text to lowercase.
- Keeps internal apostrophes (e.g., "don't") by default; set `keep_apostrophes=false` to remove them.
"""
function read_words(filepath::AbstractString; to_lowercase::Bool=true, keep_apostrophes::Bool=true)::Vector{String}
    text = read(filepath, String)
    text = to_lowercase ? lowercase(text) : text

    pattern = keep_apostrophes ?
        r"[a-zA-Z0-9]+(?:'[a-zA-Z0-9]+)*" :
        r"[a-zA-Z0-9]+"

    return [m.match for m in eachmatch(pattern, text)]
end

function count_word_frequencies(words::AbstractVector{<:AbstractString})::Dict{String, Int}
    counts = Dict{String, Int}()
    for w in words
        s = String(w)
        counts[s] = get(counts, s, 0) + 1
    end
    return counts
end

function word_freq_stats(freqs::AbstractDict{<:AbstractString,<:Integer})
    total = 0
    unique = 0
    mword = nothing
    max_count = -1
    for (w, c) in freqs
        total += c
        unique += 1
        if mword === nothing || c > max_count || (c == max_count && w < mword)
            mword = w
            max_count = c
        end
    end
    return (total_words = total, unique_words = unique, most_frequent_word = mword)
end

function generate_summary_report(stats::AbstractDict, freqs::AbstractDict{<:AbstractString,<:Integer}, N::Integer=10; title::AbstractString="Text Summary Report")
    if N < 0
        throw(ArgumentError("N must be nonnegative"))
    end

    # Helper to add thousands separators to integers
    function commify(n::Integer)
        s = string(n)
        neg = startswith(s, "-")
        if neg
            s = s[2:end]
        end
        r = reverse(s)
        buf = IOBuffer()
        len = length(r)
        for (i, c) in enumerate(r)
            write(buf, c)
            if i % 3 == 0 && i != len
                write(buf, ',')
            end
        end
        out = reverse(String(take!(buf)))
        return neg ? "-" * out : out
    end

    fmt_value(x) = x isa Integer ? commify(x) : x isa AbstractFloat ? string(round(x, digits=3)) : string(x)

    # Try to discover total token/word count for percentage calculation
    total = nothing
    for k in ("total_words", "total_tokens", "word_count", "tokens", "words", "n_tokens", "n_words")
        if haskey(stats, k)
            v = stats[k]
            if v isa Integer && v > 0
                total = v
                break
            end
        end
    end

    lines = String[]
    push!(lines, string(title))
    push!(lines, repeat("=", length(string(title))))
    push!(lines, "")

    push!(lines, "Statistics:")
    if isempty(stats)
        push!(lines, "  (none)")
    else
        for (k, v) in sort(collect(stats); by = x -> String(x[1]))
            push!(lines, "  $(k): $(fmt_value(v))")
        end
    end

    push!(lines, "")
    push!(lines, "Top $(N) words by frequency:")

    if isempty(freqs) || N == 0
        push!(lines, "  (none)")
    else
        pairs = collect(freqs)
        sort!(pairs; by = p -> (-p[2], p[1]))
        top_n = min(N, length(pairs))
        for i in 1:top_n
            w, f = pairs[i]
            line = " $(i). $(w) — $(commify(f))"
            if total !== nothing
                pct = round(100 * f / total, digits=1)
                line *= " ($(pct)%)"
            end
            push!(lines, line)
        end
    end

    return join(lines, "\n")
end

# Analyze a text file: tokenize, count word frequencies, compute stats, and generate a report

# Internal tokenizer
function _tokenize(text::AbstractString; to_lowercase::Bool=true, keep_hyphens::Bool=false, keep_apostrophes::Bool=true)
    # Choose a Unicode-aware regex for words
    # [:L:] letters, [:N:] numbers. Optionally keep internal hyphens/apostrophes.
    pattern = if keep_hyphens && keep_apostrophes
        r"[a-zA-Z0-9]+(?:[-''][a-zA-Z0-9]+)*"
    elseif keep_hyphens && !keep_apostrophes
        r"[a-zA-Z0-9]+(?:-[a-zA-Z0-9]+)*"
    elseif !keep_hyphens && keep_apostrophes
        r"[a-zA-Z0-9]+(?:[''][a-zA-Z0-9]+)*"
    else
        r"[a-zA-Z0-9]+"
    end
    tokens = String[m.match for m in eachmatch(pattern, text)]
    return to_lowercase ? lowercase.(tokens) : tokens
end

# Internal median helper
function _median_int_as_float(v::Vector{Int})
    n = length(v)
    n == 0 && return NaN
    sv = sort(v)
    if isodd(n)
        return float(sv[(n + 1) >>> 1])
    else
        i = n >>> 1
        return (sv[i] + sv[i + 1]) / 2
    end
end

# Main function
function analyze_text_file(path::AbstractString; stopwords::Set{String}=Set{String}(), top_n::Integer=20,
                           min_word_length::Integer=1, lowercase::Bool=true,
                           keep_hyphens::Bool=false, keep_apostrophes::Bool=true)
    text = read(path, String)

    # Normalize stopwords to match tokenization case behavior
    norm_stop = lowercase ? Set(lowercase.(collect(stopwords))) : stopwords

    words = _tokenize(text; to_lowercase=lowercase, keep_hyphens=keep_hyphens, keep_apostrophes=keep_apostrophes)
    # Filter by min length and stopwords
    words = [w for w in words if length(w) >= min_word_length && !(w in norm_stop)]

    # Frequencies
    counts = Dict{String,Int}()
    for w in words
        counts[w] = get(counts, w, 0) + 1
    end

    total_words = length(words)
    unique_words = length(counts)

    # Stats on word lengths (over all tokens)
    lengths = map(length, words)
    avg_word_length = total_words > 0 ? sum(lengths) / total_words : NaN
    median_word_length = _median_int_as_float(lengths)

    # Vocabulary richness and hapax
    vocab_richness = total_words > 0 ? unique_words / total_words : NaN
    hapax_count = count(==(1), values(counts))

    # Top words
    top_pairs = collect(counts)  # Vector{Pair{String,Int}}
    sort!(top_pairs, by = p -> (-p.second, p.first))
    if length(top_pairs) > top_n
        top_pairs = top_pairs[1:top_n]
    end

    # Longest and shortest (over unique words)
    longest_words = String[]
    shortest_words = String[]
    if !isempty(counts)
        # Determine lengths across unique words
        maxlen = 0
        minlen = typemax(Int)
        for w in keys(counts)
            lw = length(w)
            if lw > maxlen; maxlen = lw; end
            if lw < minlen; minlen = lw; end
        end
        longest_words = sort([w for w in keys(counts) if length(w) == maxlen])
        shortest_words = sort([w for w in keys(counts) if length(w) == minlen])
    end

    # Build report
    io = IOBuffer()
    println(io, "Text Analysis Report")
    println(io, "File: ", path)
    println(io, "----------------------------------------")
    println(io, "Total words: ", total_words)
    println(io, "Unique words: ", unique_words)
    println(io, "Vocabulary richness (unique/total): ", isnan(vocab_richness) ? "NaN" : string(round(vocab_richness; digits=4)))
    println(io, "Average word length: ", isnan(avg_word_length) ? "NaN" : string(round(avg_word_length; digits=3)))
    println(io, "Median word length: ", isnan(median_word_length) ? "NaN" : string(round(median_word_length; digits=3)))
    println(io, "Hapax legomena (freq = 1): ", hapax_count)
    if !isempty(longest_words)
        println(io, "Longest words (length ", length(first(longest_words)), "): ", join(longest_words, ", "))
    else
        println(io, "Longest words: ")
    end
    if !isempty(shortest_words)
        println(io, "Shortest words (length ", length(first(shortest_words)), "): ", join(shortest_words, ", "))
    else
        println(io, "Shortest words: ")
    end
    println(io)
    println(io, "Top ", min(top_n, length(top_pairs)), " words:")
    for (i, p) in enumerate(top_pairs)
        println(io, lpad(string(i), 3), ". ", rpad(p.first, 20), " ", p.second)
    end

    report = String(take!(io))

    return (;
        word_counts = counts,
        total_words,
        unique_words,
        avg_word_length,
        median_word_length,
        vocab_richness,
        hapax_count,
        longest_words,
        shortest_words,
        top_words = top_pairs,
        report,
    )
end