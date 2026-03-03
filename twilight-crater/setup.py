from setuptools import setup, find_packages

setup(
    name="gdut-cli",
    version="0.1.0",
    description="广东工业大学教务系统 CLI 工具",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "click>=8.0",
        "requests>=2.28",
        "beautifulsoup4>=4.12",
        "rich>=13.0",
        "python-dotenv>=1.0",
        "lxml>=4.9",
        "playwright>=1.40",
    ],
    entry_points={
        "console_scripts": [
            "gdut=jw.cli:main",
        ],
    },
)
