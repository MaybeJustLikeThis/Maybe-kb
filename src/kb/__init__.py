"""Local knowledge base CLI tool."""
import warnings

__version__ = "0.1.0"

# jieba imports pkg_resources which triggers a deprecation warning on stderr.
# MCP uses stdin/stdout for JSON-RPC — any stderr noise breaks the handshake.
warnings.filterwarnings("ignore", message=".*pkg_resources.*", category=UserWarning)
