# Universal Adapter Core

Shared contracts used by connectors, the universal adapter, and EM-safe mods.

The core package defines the neutral object model. Provider-specific code should
depend on these contracts instead of depending directly on `bicameral-mcp`
handler payloads.
