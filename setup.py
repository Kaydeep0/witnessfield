from setuptools import setup, find_packages

setup(
    name="witnessfield",
    version="1.0.1",
    author="Kirandeep Kaur",
    description="Witness structure protocol — describe claims and custody chains, score with swappable policy",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/Kaydeep0/witnessfield",
    project_urls={
        "Documentation": "https://geniusflow-federation.vercel.app/llms.txt",
        "Mode A": "https://kaydeep0.github.io/eigenstate-research/mode-a-walkthrough/",
        "Source": "https://github.com/Kaydeep0/witnessfield",
    },
    license="MIT",
    packages=find_packages(),
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
