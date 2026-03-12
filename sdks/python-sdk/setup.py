from setuptools import setup, find_packages

setup(
    name="visionforge-sdk",
    version="1.0.0",
    description="VisionForge Machine Vision Platform Python SDK",
    author="VisionForge",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "requests>=2.31.0",
        "numpy>=1.24.0",
        "Pillow>=10.0.0",
    ],
    extras_require={
        "onnx": ["onnxruntime>=1.17.0"],
        "cv": ["opencv-python-headless>=4.9.0"],
    },
)
