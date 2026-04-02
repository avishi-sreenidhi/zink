from pathlib import Path
from setuptools import setup, find_packages

setup(
    name="zink",
    version="0.2.0",
    description="Deterministic runtime governance middleware for AI agents",
    long_description=(
        Path("README.md").read_text(encoding="utf-8")
        if Path("README.md").exists()
        else ""
    ),
    long_description_content_type="text/markdown",
    author="Avishi Sreenidhi",
    license="MIT",
    url="https://github.com/avishi/zink",
    project_urls={
        "Documentation": "https://github.com/avishi/zink#readme",
        "Issues":        "https://github.com/avishi/zink/issues",
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Security",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    packages=find_packages(exclude=["tests*", "examples*", "demo*"]),
    python_requires=">=3.10",

    # Core dependencies — installed for everyone
    install_requires=[
        "pydantic>=2.10.0",
        "pyyaml>=6.0",
        "pyparsing>=3.0.0",
    ],

    extras_require={
        # Framework adapters
        "langchain": [
            "langchain>=0.3.0",
            "langchain-core>=0.3.0",
            "langgraph>=0.4.0",
        ],
        # CLI tools
        "cli": [
            "click>=8.1.0",
            "rich>=13.0.0",
        ],
        # Dashboard
        "dashboard": [
            "fastapi>=0.110.0",
            "uvicorn>=0.29.0",
            "websockets>=12.0",
        ],
        # Running the examples
        "examples": [
            "langchain>=0.3.0",
            "langchain-core>=0.3.0",
            "langgraph>=0.4.0",
            "langchain-google-genai>=4.2.0",
            "python-dotenv>=1.0.0",
            "httpx>=0.27.0",
        ],
        # Development
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "black>=24.0.0",
            "mypy>=1.0.0",
        ],
        # Everything — flattened, no self-references
        "all": [
            "langchain>=0.3.0",
            "langchain-core>=0.3.0",
            "langgraph>=0.4.0",
            "langchain-google-genai>=4.2.0",
            "python-dotenv>=1.0.0",
            "httpx>=0.27.0",
            "click>=8.1.0",
            "rich>=13.0.0",
            "fastapi>=0.110.0",
            "uvicorn>=0.29.0",
            "websockets>=12.0",
        ],
    },

    entry_points={
        "console_scripts": [
            "zink=zink.cli.main:cli",   # `zink audit`, `zink verify`, etc.
        ],
    },
)