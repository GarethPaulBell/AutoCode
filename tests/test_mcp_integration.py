import json
import code_db
from src.autocode.mcp_autocode_server import AutoCodeMCPServer


def call_tool(server: AutoCodeMCPServer, name: str, arguments: dict, call_id=1):
    req = {
        "jsonrpc": "2.0",
        "id": call_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments}
    }
    resp = server.handle_request(req)
    return resp


def test_mcp_find_cycles_and_recursion_and_remove_dependency():
    # Ensure MCP mode is set to avoid print spamming
    import os
    os.environ["MCP_AUTOCODE_MODE"] = "1"
    server = AutoCodeMCPServer()

    # Create functions via code_db public API (registered commands are available via code_db)
    f1_id = code_db.add_function('mcp_a', 'mcp a', 'mcp_a(x) = x')
    f2_id = code_db.add_function('mcp_b', 'mcp b', 'mcp_b(x) = x')

    # Add dependency f1 -> f2 via code_db wrapper
    res = code_db.add_dependency(f1_id, f2_id)
    assert isinstance(res, dict) and res.get('success')

    # Call find_cycles via MCP tool (should return empty cycles list)
    resp = call_tool(server, 'find_cycles', {})
    assert resp and 'result' in resp
    result_content = resp['result']['content'][0]['json']
    assert isinstance(result_content.get('cycles'), list)

    # Create a direct recursive function and test detect_recursion via MCP
    code = """
function rec(x)
  return rec(x-1)
end
"""
    rec_id = code_db.add_function('rec', 'recursive', code)
    resp2 = call_tool(server, 'detect_recursion', {'function_id': rec_id})
    assert resp2 and 'result' in resp2
    det = resp2['result']['content'][0]['json']
    assert isinstance(det, dict) and det.get('direct') is True

    # Test remove_dependency via MCP call (remove f1 -> f2)
    resp3 = call_tool(server, 'remove_dependency', {'function_id': f1_id, 'depends_on_id': f2_id})
    assert resp3 and 'result' in resp3
    rem = resp3['result']['content'][0]['json']
    assert isinstance(rem, dict) and rem.get('success') is True
