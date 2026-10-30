from app.rag.ast_parser import PythonASTParser


def test_ast_parser_extracts_functions_and_classes():
    code = """
import os

class AuthService:
    \"\"\"Manages user authentication.\"\"\"

    def __init__(self, secret: str):
        self.secret = secret

    async def verify_token(self, token: str) -> bool:
        return True

def calculate(x, y):
    return x + y
"""
    parser = PythonASTParser()
    symbols = parser.extract_symbols(code)

    names = {s.name for s in symbols}
    kinds = {s.name: s.kind for s in symbols}

    assert "AuthService" in names
    assert kinds["AuthService"] == "class"
    assert "verify_token" in names
    assert kinds["verify_token"] == "async_function"
    assert "calculate" in names
    assert kinds["calculate"] == "function"
    assert "x" in [s for s in symbols if s.name == "calculate"][0].parameters


def test_ast_parser_handles_syntax_error_gracefully():
    malformed_code = "def invalid_syntax(:"
    parser = PythonASTParser()
    symbols = parser.extract_symbols(malformed_code)
    assert symbols == []
