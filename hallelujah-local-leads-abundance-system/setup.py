from setuptools import setup, find_packages

setup(
    name="hallelujah-local-leads",
    version="1.0.0",
    description="Automated local business lead generation from Chambers, BNI, and Magazines",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "playwright>=1.40.0",
        "beautifulsoup4>=4.12.0",
        "requests>=2.31.0",
        "python-dotenv>=1.0.0",
    ],
)
