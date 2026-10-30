"""Broken on purpose: imports `greeter` but the module file is greeting.py."""

from greeter import greet


def run(name: str = "Ada") -> str:
    return greet(name)


if __name__ == "__main__":
    print(run())
