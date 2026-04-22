from setuptools import setup, find_packages

setup(
    name="witnessfield",
    version="0.1.0",
    author="Kirandeep Kaur",
    description="Witness Field Protocol v2.1 — computable evidence scoring",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    license="MIT",
    packages=find_packages(),
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
    ],
)
