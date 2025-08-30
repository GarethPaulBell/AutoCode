#!/usr/bin/env python3
import subprocess
import json
import sys

# Test function generation request
request = {
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
        "name": "generate_function",
        "arguments": {
            "description": "simple function to add two numbers",
            "module": "math_utils"
        }
    }
}

# Start the MCP server
proc = subprocess.Popen(
    [sys.executable, "src/autocode/mcp_autocode_server.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    cwd="c:\\Users\\GGPC\\Documents\\GitHub\\AutoCode"
)

# Send the request
proc.stdin.write(json.dumps(request) + "\n")
proc.stdin.flush()

# Read the response (may take a moment for AI generation)
response = proc.stdout.readline()
proc.terminate()

print("Response:", response)

# Check if response is valid JSON
try:
    parsed = json.loads(response.strip())
    print("✅ Valid JSON response")
    if "result" in parsed:
        print("Function generated successfully")
    elif "error" in parsed:
        print("Error:", parsed["error"])
except json.JSONDecodeError as e:
    print("❌ Invalid JSON response:", e)
    print("Raw response:", repr(response))
