from setuptools import setup

version = "1.1.1"

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="aioarxiv",
    version=version,
    packages=["aioarxiv"],
    # dependencies
    python_requires=">=3.8",
    install_requires=["feedparser~=6.0.10", "aiohttp>=3.8.1"],
    tests_require=["pytest", "pdoc", "ruff"],
    # metadata for upload to PyPI
    author="Maurice Meus",
    author_email="mauricemeus@gmail.com",
    description="Asynchronous Python wrapper for the arXiv API: https://arxiv.org/help/api/",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license="MIT",
    keywords="arxiv api wrapper academic journals papers async asynchronous",
    url="https://github.com/jmmeus/aioarxiv",
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Framework :: AsyncIO",
    ],
)
