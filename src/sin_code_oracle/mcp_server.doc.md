# `mcp_server.py` — MCP Server for the Verification Oracle

What this file does: exposes two tools over the Model Context Protocol (stdio transport) so an agent can call the oracle directly: `verify_change` and `run_diagnostics`.

## Dependency map

- Optional runtime dep: `mcp[cli]>=1.2` (install via `pip install 'sin-code-oracle[mcp]'`)
- Imports: `diagnostics.DiagnosticsOracle`, `oracle.VerificationOracle`
- Entry point: `main()` — also exposed via the CLI's `oracle serve` subcommand.

## Tools exposed

| Tool                | Inputs                                                                                | Returns                                |
|---------------------|---------------------------------------------------------------------------------------|----------------------------------------|
| `verify_change`     | `root`, `test_command?`, `build_command?`, `run_diagnostics=true`, `expected_behavior_change=false` | JSON `Verdict` with `passed`, `verified`, `confidence`, `reasons` |
| `run_diagnostics`   | `root`                                                                                | JSON `DiagnosticsReport`               |

## Important config / limits

- **Transport: stdio.** The server reads JSON-RPC on stdin and writes to stdout. Use an MCP client (Claude Desktop, opencode, etc.) to talk to it.
- **Optional dep.** `FastMCP` is imported lazily; the rest of the package works without it. `main()` raises `RuntimeError` if the dep is missing.
- **No state.** Every tool call instantiates a fresh `VerificationOracle` / `DiagnosticsOracle`. There is no caching or session memory between calls.

## Design decisions

- **Why MCP?** It's the protocol coding agents already speak. Wrapping the oracle as MCP tools means agents can call `verify_change` before declaring a task done, with no glue code on either side.
- **Why return JSON strings instead of structured content?** `FastMCP` tool results are stringly-typed; serializing the verdict is the simplest contract.
- **Why is `mcp` optional?** Not every consumer of `sin-code-oracle` uses MCP. Keeping the extra optional avoids forcing the dep on CI pipelines that only use the CLI or library API.

## Usage

```bash
# 1. Install with MCP support
pip install 'sin-code-oracle[mcp]'

# 2. Start the server (stdio transport)
oracle serve

# 3. Or invoke directly from an MCP-aware agent
#    (the agent sees `verify_change` and `run_diagnostics` as tools)
```

## Caveats / footguns

- **The server is blocking and single-threaded.** Don't expect to serve multiple agents from one process.
- **No authentication / authorization.** Anyone with stdio access to the process can call the tools. Run the server in a trusted environment.
- **Tool calls can take a long time.** `verify_change` runs subprocesses (bandit, ruff, pytest) and may block for the full `default_timeout` of the underlying ExecutionOracle. Make sure your MCP client has a generous request timeout.
