import argparse
import os
import sys
from pathlib import Path

VERSION = "1.0.0-alpha"

def resolve_persona_path():
    # Support source checkouts, editable installs, and the data-file install location.
    candidates = []
    # In a PyInstaller-frozen Windows install, the persona is installed beside
    # lml.exe by setup.iss, not inside the temporary _MEIPASS bundle directory.
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "lml_persona.md")

    candidates.extend([
        Path(__file__).resolve().with_name("lml_persona.md"),
        Path.cwd() / "lml_persona.md",
        Path(sys.prefix) / "share" / "lml" / "lml_persona.md",
    ])
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return candidates[0].resolve()


def load_required_persona(parser):
    # The persona is mandatory and must contain usable instructions.
    persona_path = resolve_persona_path()
    if not persona_path.is_file():
        parser.error(f"required persona file does not exist: {persona_path}")
    try:
        persona_content = persona_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        parser.error(f"could not read persona file {persona_path}: {exc}")
    if not persona_content:
        parser.error(f"persona file is empty: {persona_path}")
    return persona_path, persona_content


def analyze_dataset(dataset_path, raw_data, device):
    # Report actual file size and loaded JSONL characteristics.
    file_size = os.path.getsize(dataset_path)
    keys = sorted({str(key) for row in raw_data for key in row})
    print("\n" + "=" * 48)
    print(" LML PRE-FLIGHT DATASET ANALYSIS")
    print("=" * 48)
    print(f" Dataset file : {os.path.abspath(dataset_path)}")
    print(f" File size    : {file_size / (1024 * 1024):.2f} MiB")
    print(f" JSONL rows   : {len(raw_data)}")
    print(f" Field names  : {', '.join(keys) if keys else '(none)'}")
    print(f" Device       : {device}")
    print("=" * 48 + "\n")


def print_custom_help():
    print("Usage (--logging is optional):")
    print("  lml --dataset <path> --ftllm <path> --verifier-llm <path> --save_dir <path> --max-length <tokens> --logging <path>")
    print("  lml --version")
    print("  lml help")


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="lml",
        description="LML alpha: AI-generated tokenizer and training pipeline with separate AI review.",
    )
    parser.add_argument("--version", action="version", version=f"LML {VERSION}")
    parser.add_argument("--dataset", type=str, help="Path to the JSONL training dataset")
    parser.add_argument("--ftllm", type=str, help="Path to the local generator/factory model")
    parser.add_argument("--verifier-llm", type=str, help="Path to a separate local code-review model")
    parser.add_argument("--save_dir", type=str, help="Directory for generated artifacts and the trained model")
    parser.add_argument("--max-length", type=int, help="Maximum token sequence length")
    parser.add_argument("--logging", type=str, default=None, help="Directory path to save logs")
    parser.add_argument("command", nargs="?", help=argparse.SUPPRESS)

    args = parser.parse_args(argv)
    if args.command == "help":
        print_custom_help()
        return 0

    required = {
        "--dataset": args.dataset,
        "--ftllm": args.ftllm,
        "--verifier-llm": args.verifier_llm,
        "--save_dir": args.save_dir,
        "--max-length": args.max_length,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        parser.error("the following arguments are required: " + ", ".join(missing))
    if args.max_length < 8:
        parser.error("--max-length must be at least 8")
    if not os.path.isfile(args.dataset):
        parser.error(f"dataset file does not exist: {args.dataset}")
    if not os.path.isdir(args.ftllm):
        parser.error(f"generator model path must be a local directory: {args.ftllm}")
    if not os.path.isdir(args.verifier_llm):
        parser.error(f"verifier model path must be a local directory: {args.verifier_llm}")

    # Fail before loading large ML models if the required persona is missing.
    persona_path, persona_content = load_required_persona(parser)

    try:
        import lml_config
        from lml_core import LMLPipeline
        from lml_dataset_loader import DatasetLoader
        from lml_utils import Logger

        raw_data = DatasetLoader(args.dataset).load_data()
        import lml_config
        analyze_dataset(args.dataset, raw_data, lml_config.DEVICE)
        if args.logging:
            Logger.log("LML v1.0.0-alpha pipeline started.", args.logging)

        pipeline = LMLPipeline(
            generator_path=args.ftllm,
            verifier_path=args.verifier_llm,
            dataset_path=args.dataset,
            save_dir=args.save_dir,
            max_length=args.max_length,
            persona_content=persona_content,
            persona_path=str(persona_path),
        )
        pipeline.run(raw_data)
        if args.logging:
            Logger.log("LML pipeline completed.", args.logging)
        return 0
    except KeyboardInterrupt:
        print("\n[!] Interrupted by user.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        if args.logging:
            from lml_utils import Logger
            Logger.log(f"ERROR: {exc}", args.logging)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
