from setuptools import setup

setup(
    name="intellishell",
    version="0.4.0",
    package_dir={"": "src"},
    py_modules=["insh"],
    install_requires=[
        "prompt_toolkit"
    ],
    author="Lifailon",
    description="This is a handler that runs on top of the Bash shell and implements command autocomplete using a dropdown list in real time.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/Lifailon/intellishell",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    entry_points={
        "console_scripts": [
            "insh=insh:main",
        ],
    },
)