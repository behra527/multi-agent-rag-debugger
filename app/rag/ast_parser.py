import ast
from dataclasses import dataclass, field


@dataclass
class SymbolInfo:
    """Represents a code symbol extracted from an AST."""

    name: str
    kind: str  # "class", "function", "async_function", "method"
    start_line: int
    end_line: int
    docstring: str | None = None
    parameters: list[str] = field(default_factory=list)


class PythonASTParser:
    """Extracts structural symbols and spans from Python source code."""

    def extract_symbols(self, code: str) -> list[SymbolInfo]:
        """Parse Python source and extract function and class declarations."""
        try:
            tree = ast.parse(code)
        except (SyntaxError, UnicodeDecodeError, ValueError):
            return []

        symbols: list[SymbolInfo] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                end_lineno = getattr(node, "end_lineno", node.lineno)
                doc = ast.get_docstring(node)
                symbols.append(
                    SymbolInfo(
                        name=node.name,
                        kind="class",
                        start_line=node.lineno,
                        end_line=end_lineno,
                        docstring=doc,
                    )
                )
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                end_lineno = getattr(node, "end_lineno", node.lineno)
                doc = ast.get_docstring(node)
                kind = "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function"
                params = [arg.arg for arg in node.args.args]
                symbols.append(
                    SymbolInfo(
                        name=node.name,
                        kind=kind,
                        start_line=node.lineno,
                        end_line=end_lineno,
                        docstring=doc,
                        parameters=params,
                    )
                )

        return sorted(symbols, key=lambda s: s.start_line)
