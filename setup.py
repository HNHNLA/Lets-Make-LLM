from setuptools import setup

setup(
    name="lml",
    version="1.0.0a0",
    description="Let's Make LLM - AI-assisted model training pipeline",
    py_modules=[
        "lml_core",
        "lml_engine",
        "lml_config",
        "lml_dataset_loader",
        "lml_utils",
    ],
    data_files=[("share/lml", ["lml_persona.md"])],
    install_requires=[
        "transformers>=4.40.0",
        "torch",
        "datasets",
        "accelerate",
        "tokenizers",
    ],
    entry_points={
        "console_scripts": ["lml=lml_engine:main"],
    },
    python_requires=">=3.10",
)
