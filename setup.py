#!/usr/bin/env python
# -*- encoding: utf-8 -*-
from __future__ import absolute_import, print_function

import io
import re
from glob import glob
from os.path import basename, dirname, join, splitext

from setuptools import find_packages, setup


def read(*names, **kwargs):
    return io.open(
        join(dirname(__file__), *names), encoding=kwargs.get("encoding", "utf8")
    ).read()


def find_version(*file_paths):
    contents = read(*file_paths)
    match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", contents, re.M)
    if match:
        return match.group(1)
    raise RuntimeError("Unable to find version string.")


setup(
    name="awsrun",
    python_requires=">=3.7",
    version=find_version("src", "awsrun", "__init__.py"),
    license="",
    description="CLI to execute user-defined commands across one or more AWS accounts",
    long_description="""`awsrun` is both a CLI and library to execute commands over one or more AWS accounts
concurrently. Commands are user-defined Python modules that implement a simple
interface to abstract away the complications of obtaining credentials for Boto3
sessions - especially when using SAML authentication and/or cross-account
access.""",
    long_description_content_type="text/markdown",
    author="Pete Kazmier",
    author_email="opensource@fidelity.com",
    url="https://github.com/fidelity/awsrun",
    packages=find_packages("src"),
    package_dir={"": "src"},
    py_modules=[splitext(basename(path))[0] for path in glob("src/*.py")],
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        # complete classifier list: http://pypi.python.org/pypi?%3Aaction=list_classifiers
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Unix",
        "Operating System :: POSIX",
        "Operating System :: Microsoft :: Windows",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: Implementation :: CPython",
        "Topic :: Utilities",
    ],
    keywords=["awsrun", "aws", "cli"],
    install_requires=[
        "boto3>=1.12.39",
        "azure-identity",
        "azure-mgmt-network",
        "bs4",
        "colorama",
        "asciichartpy>=1.5.14",
        "pysparklines>=1.0",
        "py_cui==0.0.3",
        "requests_file",
        "requests_ntlm",
        "requests",
        "PyYAML>=3.10",
    ],
    tests_require=["pytest", "pytest-mock", "freezegun"],
    extras_require={},
    entry_points={
        "console_scripts": [
            "awsrun = awsrun.cli:main",
            "azurerun = awsrun.cli:main",
        ]
    },
)
