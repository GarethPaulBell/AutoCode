include("text_analyzer.jl")

# Test the functions
println("Testing read_words...")
words = read_words("sample_text.txt")
println("Words: ", words)

println("\nTesting count_word_frequencies...")
freqs = count_word_frequencies(words)
println("Frequencies: ", freqs)

println("\nTesting word_freq_stats...")
stats = word_freq_stats(freqs)
println("Stats: ", stats)

println("\nTesting generate_summary_report...")
stats_dict = Dict("total_words" => stats.total_words, "unique_words" => stats.unique_words, "most_frequent_word" => stats.most_frequent_word)
report = generate_summary_report(stats_dict, freqs, 5)
println("Report:\n", report)

println("\nTesting analyze_text_file...")
result = analyze_text_file("sample_text.txt")
println("Full analysis report:\n", result.report)