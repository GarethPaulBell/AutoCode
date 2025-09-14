module recipe_manager

# Function: add_recipe
# Description: Validate inputs, store a recipe with a unique ID in a global registry, and return the ID.
# Global storage for recipes and a lock for thread-safety
using UUIDs
using Dates

# Global registry for recipes: id => recipe dict
RECIPES = Dict{String, Dict{String,Any}}()
RECIPES_LOCK = ReentrantLock()

# Internal helper to validate and normalize a single ingredient
function _normalize_ingredient(ing)::Dict{String,Any}
    if !(ing isa AbstractDict)
        throw(ArgumentError("Each ingredient must be a dictionary with keys 'name' and 'quantity'."))
    end
    has_name = haskey(ing, "name") || haskey(ing, :name)
    has_qty  = haskey(ing, "quantity") || haskey(ing, :quantity)
    if !has_name || !has_qty
        throw(ArgumentError("Ingredient missing required keys 'name' and 'quantity'."))
    end
    iname = haskey(ing, "name") ? ing["name"] : ing[:name]
    iqty  = haskey(ing, "quantity") ? ing["quantity"] : ing[:quantity]

    if !(iname isa AbstractString) || isempty(strip(String(iname)))
        throw(ArgumentError("Ingredient 'name' must be a non-empty string."))
    end

    if iqty isa AbstractString
        if isempty(strip(iqty))
            throw(ArgumentError("Ingredient 'quantity' string must be non-empty."))
        end
    elseif !(iqty isa Real)
        throw(ArgumentError("Ingredient 'quantity' must be a string or a real number."))
    end

    return Dict{String,Any}("name" => String(iname), "quantity" => iqty)
end

"""
    add_recipe(name::String, ingredients::Vector{<:AbstractDict}, instructions::String) -> String

Validate inputs and store the recipe in a global registry under a unique ID.
Returns the recipe ID as a String.
"""
function add_recipe(name::String, ingredients::Vector{<:AbstractDict}, instructions::String)::String
    n = strip(name)
    if isempty(n)
        throw(ArgumentError("Recipe name must be a non-empty string."))
    end

    if ingredients === nothing || isempty(ingredients)
        throw(ArgumentError("Ingredients must be a non-empty vector of dictionaries."))
    end

    norm_ings = Vector{Dict{String,Any}}(undef, length(ingredients))
    for (i, ing) in pairs(ingredients)
        norm_ings[i] = _normalize_ingredient(ing)
    end

    inst = strip(instructions)
    if isempty(inst)
        throw(ArgumentError("Instructions must be a non-empty string."))
    end

    id = string(uuid4())
    recipe = Dict{String,Any}(
        "id" => id,
        "name" => n,
        "ingredients" => norm_ings,
        "instructions" => inst,
        "created_at" => Dates.format(Dates.now(), DateFormat("yyyy-mm-ddTHH:MM:SS")),
    )

    lock(RECIPES_LOCK) do
        RECIPES[id] = recipe
    end

    return id
end

# Test: add_recipe_stores_and_returns_id
# Adds a recipe and verifies the ID is returned and the recipe is stored in the global registry.
empty!(RECIPES)
id = add_recipe("Pancakes", [Dict("name"=>"Flour","quantity"=>"2 cups"), Dict(:name=>"Milk", :quantity=>"1 cup")], "Mix and cook.")
@assert haskey(RECIPES, id) && RECIPES[id]["name"] == "Pancakes" && isa(id, String)

# Function: search_recipes_by_ingredient
# Description: Search RECIPES for recipe IDs whose ingredients include the given ingredient, case-insensitive.
"""
search_recipes_by_ingredient(ingredient_name::String) -> Vector{String}
Searches global RECIPES dictionary for recipes whose ingredients contain the query string case-insensitively.
The RECIPES dictionary is expected to map recipe IDs (String) to recipe data that include an "ingredients" field, e.g.:
 - Dict(:ingredients => ["Sugar", "Flour", ...])
 - Dict(:ingredients => [ (name="Brown Sugar",), ... ])
 - Dict(:ingredients => [ Dict("name"=>"Sugar"), ... ])
Returns a Vector{String} of recipe IDs; empty if none or if RECIPES is not defined.
"""
function search_recipes_by_ingredient(ingredient_name::String)::Vector{String}
    term = lowercase(strip(ingredient_name))
    if isempty(term)
        return String[]
    end

    # Ensure the global RECIPES dictionary exists in the current module
    if !isdefined(@__MODULE__, :RECIPES)
        return String[]
    end
    recipes = getfield(@__MODULE__, :RECIPES)

    # If RECIPES isn't a dictionary-like collection, bail out safely
    if !(recipes isa AbstractDict)
        return String[]
    end

    results = String[]
    for (rid, data) in recipes
        names = _srbi_extract_ingredient_names(data)
        if any(n -> occursin(term, lowercase(n)), names)
            push!(results, String(rid))
        end
    end
    return results
end

# Internal helper: extract ingredient names as strings from a variety of common structures
function _srbi_extract_ingredient_names(data)::Vector{String}
    # Fetch possible ingredients collections from various container types
    raw = nothing
    if data isa AbstractDict
        if haskey(data, :ingredients)
            raw = data[:ingredients]
        elseif haskey(data, "ingredients")
            raw = data["ingredients"]
        end
    elseif data isa NamedTuple
        if hasproperty(data, :ingredients)
            raw = getproperty(data, :ingredients)
        end
    end

    names = String[]
    if raw isa AbstractVector
        for el in raw
            if el isa AbstractString
                push!(names, String(el))
            elseif el isa AbstractDict
                if haskey(el, :name) && (el[:name] isa AbstractString)
                    push!(names, String(el[:name]))
                elseif haskey(el, "name") && (el["name"] isa AbstractString)
                    push!(names, String(el["name"]))
                end
            elseif el isa NamedTuple
                if hasproperty(el, :name)
                    v = getproperty(el, :name)
                    if v isa AbstractString
                        push!(names, String(v))
                    end
                end
            end
        end
    end
    return names
end

# Test: search_recipes_by_ingredient_case_insensitive_match
# Verifies it returns recipe IDs whose ingredients include the substring "sugar" ignoring case.
# Setup a sample global RECIPES dictionary
RECIPES = Dict(
    "r1" => Dict(:name => "Pancakes", :ingredients => ["Flour", "Eggs", "Milk", "Sugar"]),
    "r2" => Dict(:name => "Salad", :ingredients => [ (name = "Olive Oil",), (name = "Lemon Juice",), (name = "salt",) ]),
    "r3" => Dict(:name => "BBQ Rub", :ingredients => [ Dict("name" => "Brown Sugar"), Dict("name" => "Paprika") ])
)

@assert sort(search_recipes_by_ingredient("sugar")) == ["r1","r3"]

# Function: calculate_recipe_cost
# Description: Compute total recipe cost from global RECIPES and given ingredient prices, handling missing data gracefully.
# Global RECIPES dictionary mapping recipe_id => Dict(ingredient => quantity)
const RECIPES = Dict(
    "pancakes" => Dict("flour" => 2.0, "milk" => 1.5, "egg" => 2.0),
    "salad"    => Dict("lettuce" => 1.0, "tomato" => 2.0, "olive_oil" => 0.05),
)

"""
    calculate_recipe_cost(recipe_id::String, ingredient_prices::Dict{String, Float64}) -> Float64

Look up the recipe in the global RECIPES dict, then compute the total cost by
summing quantity * price for each ingredient. If the recipe is not found,
or if some ingredient prices are missing, handle gracefully by returning 0.0
for missing recipe and skipping missing-priced ingredients (emitting a warning).
"""
function calculate_recipe_cost(recipe_id::String, ingredient_prices::Dict{String, Float64})::Float64
    # Ensure RECIPES exists and is usable
    if !@isdefined RECIPES
        @warn "RECIPES global is not defined. Returning 0.0."
        return 0.0
    end
    recipes = RECIPES
    if !(recipes isa AbstractDict)
        @warn "RECIPES is not a dictionary-like mapping. Returning 0.0."
        return 0.0
    end

    # Find the recipe
    if !haskey(recipes, recipe_id)
        @warn "Recipe '$(recipe_id)' not found in RECIPES. Returning 0.0."
        return 0.0
    end

    recipe = recipes[recipe_id]
    if !(recipe isa AbstractDict{<:AbstractString,<:Real})
        @warn "Recipe '$(recipe_id)' is not a mapping of ingredient=>quantity. Returning 0.0."
        return 0.0
    end

    total::Float64 = 0.0
    missing = String[]
    for (ingredient, qty_any) in recipe
        qty = float(qty_any)
        price = get(ingredient_prices, ingredient, nothing)
        if price === nothing
            push!(missing, ingredient)
            continue
        end
        total += qty * price
    end

    if !isempty(missing)
        @warn "Missing prices for ingredients: $(join(missing, ", ")). These were skipped."
    end

    return total
end

# Test: calculate_recipe_cost_handles_missing_and_valid
# Computes correct totals and gracefully skips missing ingredient prices.
# Prices for ingredients (intentionally omit olive_oil to test graceful handling)
prices = Dict(
    "flour" => 1.2,
    "milk" => 0.8,
    "egg" => 0.3,
    "lettuce" => 0.5,
    "tomato" => 0.4,
)

# Pancakes: 2.0*1.2 + 1.5*0.8 + 2.0*0.3 = 2.4 + 1.2 + 0.6 = 4.2
@assert isapprox(calculate_recipe_cost("pancakes", prices), 4.2; atol=1e-9)

# Salad with missing olive_oil price should skip it: 1.0*0.5 + 2.0*0.4 = 1.3
@assert isapprox(calculate_recipe_cost("salad", prices), 1.3; atol=1e-9)

# Function: save_recipes_to_file
# Description: Serialize the global RECIPES dictionary to JSON and save it to a file, returning true on success and false on failure.
using JSON

function save_recipes_to_file(filename::String)::Bool
    try
        json_str = JSON.json(RECIPES)
        open(filename, "w") do io
            write(io, json_str)
        end
        return true
    catch
        return false
    end
end

# Test: save_recipes_to_file_writes_json
# Ensures the function writes RECIPES to a file and the JSON content is correct.
using JSON
# Prepare a sample global RECIPES dictionary
global RECIPES = Dict{String,Any}(
    "pancakes" => Dict{String,Any}(
        "ingredients" => ["flour", "eggs", "milk"],
        "time" => 15
    ),
    "soup" => Dict{String,Any}(
        "ingredients" => ["water", "salt"],
        "time" => 30
    )
)

# Use a temporary directory for testing
tmpdir = mktempdir()
filepath = joinpath(tmpdir, "recipes.json")

result = save_recipes_to_file(filepath)
@assert result == true && isfile(filepath)

# Verify content
parsed = JSON.parse(read(filepath, String))
@assert haskey(parsed, "pancakes") && parsed["pancakes"]["time"] == 15

# Function: load_recipes_from_file
# Description: Load recipes from a JSON file into the global RECIPES dictionary, returning true on success and false on failure.
using JSON

# Global recipes dictionary
const RECIPES = Dict{String,Any}()

"""
    load_recipes_from_file(filename::String) -> Bool

Read a JSON file at `filename`, parse it, and update the global `RECIPES` dictionary.
Accepts either a JSON object mapping recipe names to recipe data, or an array of objects
with a "name" field. Returns true on success, false on failure. On failure, `RECIPES`
remains unchanged.
"""
function load_recipes_from_file(filename::String)::Bool
    try
        parsed = JSON.parsefile(filename)

        # Build a new mapping so we only update RECIPES on total success
        newmap = Dict{String,Any}()
        if isa(parsed, AbstractDict)
            # Expecting {"recipe_name": {...}, ...}
            for (k, v) in parsed
                newmap[string(k)] = v
            end
        elseif isa(parsed, AbstractVector)
            # Accept [{"name": "...", ...}, ...]
            for item in parsed
                if isa(item, AbstractDict) && haskey(item, "name")
                    name = item["name"]
                    newmap[string(name)] = item
                else
                    return false
                end
            end
        else
            return false
        end

        # Update the global RECIPES atomically
        empty!(RECIPES)
        merge!(RECIPES, newmap)
        return true
    catch
        return false
    end
end

# Test: load_recipes_from_file_basic_success
# Loads a simple JSON object into RECIPES and verifies contents.
# Create a temporary JSON file and verify loading updates RECIPES
content = """{"Pancakes": {"servings": 2}, "Soup": {"servings": 4}}"""
mktemp() do path, io
    write(io, content)
    close(io)
    ok = load_recipes_from_file(path)
    @assert ok
    @assert haskey(RECIPES, "Pancakes")
    @assert RECIPES["Soup"]["servings"] == 4
end

# Function: setup_recipe_manager
# Description: Defines Ingredient and Recipe structs and a global RECIPES dictionary.
function setup_recipe_manager(; module_target::Module = @__MODULE__)
    m = module_target
    # Define Ingredient struct if not already defined
    if !isdefined(m, :Ingredient)
        Core.eval(m, quote
            struct Ingredient
                name::String
                quantity::String
            end
        end)
    end
    # Define Recipe struct if not already defined
    if !isdefined(m, :Recipe)
        Core.eval(m, quote
            struct Recipe
                id::Int
                name::String
                ingredients::Vector{Ingredient}
                instructions::String
            end
        end)
    end
    # Define global RECIPES dictionary if not already defined
    if !isdefined(m, :RECIPES)
        Core.eval(m, :(const RECIPES = Dict{Int, Recipe}()))
    end
    return (
        Ingredient = getfield(m, :Ingredient),
        Recipe = getfield(m, :Recipe),
        RECIPES = getfield(m, :RECIPES),
    )
end

# Test: define_core_structs_and_global_dict
# Defines structs and ensures RECIPES stores and retrieves a Recipe.
let S = setup_recipe_manager()
    Ingredient, Recipe, RECIPES = S.Ingredient, S.Recipe, S.RECIPES
    ing1 = Ingredient("Flour", "2 cups")
    ing2 = Ingredient("Sugar", "1 cup")
    r = Recipe(1, "Cake", [ing1, ing2], "Mix and bake.")
    RECIPES[r.id] = r
    @assert RECIPES[1].name == "Cake" && length(RECIPES[1].ingredients) == 2 && RECIPES isa Dict{Int, Recipe}
end

end # module recipe_manager
