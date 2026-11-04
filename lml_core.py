import gc
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

import lml_config
from lml_dataset_loader import write_cleaned_jsonl
from lml_utils import extract_code, extract_json, validate_generated_python

class LMLCore:
    def __init__(self, model_path, role="generator"):
        self.path = model_path
        self.role = role
        self.device = lml_config.DEVICE
        self.model = None
        self.tokenizer = None

    def load_model(self):
        # Load the language model assigned to this pipeline role from local files.
        print(f"[i] Loading {self.role} model on {self.device}: {self.path}")
        self.tokenizer = AutoTokenizer.from_pretrained(self.path, local_files_only=True)
        if self.tokenizer.pad_token is None and self.tokenizer.eos_token is not None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        load_args = {"local_files_only": True}
        if self.device == "cuda":
            load_args["torch_dtype"] = torch.float16
            load_args["device_map"] = "auto"
        else:
            load_args["torch_dtype"] = torch.float32
        self.model = AutoModelForCausalLM.from_pretrained(self.path, **load_args)
        if self.device in {"xpu", "cpu"}:
            self.model.to(self.device)
        self.model.eval()

    def unload_model(self):
        # Release model memory between generation and verification phases.
        if self.model is not None:
            del self.model
            self.model = None
        if self.tokenizer is not None:
            del self.tokenizer
            self.tokenizer = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        if hasattr(torch, "xpu") and torch.xpu.is_available():
            try:
                torch.xpu.empty_cache()
            except (AttributeError, RuntimeError):
                pass

    def generate(self, prompt, system_prompt="", max_len=1200):
        # Generate one response from the currently loaded model.
        if self.model is None or self.tokenizer is None:
            raise RuntimeError(f"The {self.role} model is not loaded.")
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
        if getattr(self.tokenizer, "chat_template", None):
            rendered = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        else:
            rendered = f"System: {system_prompt}\nUser: {prompt}\nAssistant:"
        inputs = self.tokenizer(rendered, return_tensors="pt")
        input_device = next(self.model.parameters()).device
        inputs = {key: value.to(input_device) for key, value in inputs.items()}
        generation_args = {
            "max_new_tokens": max_len,
            "do_sample": False,
        }
        if self.tokenizer.pad_token_id is not None:
            generation_args["pad_token_id"] = self.tokenizer.pad_token_id
        with torch.inference_mode():
            output = self.model.generate(**inputs, **generation_args)
        return self.tokenizer.decode(
            output[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True
        ).strip()

    def verify_code(self, code, task_description, output_dir=None, max_len=900):
        # Ask the separate verifier model to review code without executing it.
        prompt = (
            "Review the Python code below. Return ONLY a JSON object with keys "
            '"approved" (boolean), "issues" (array of strings), and "summary" (string). '
            "Reject code that does not fulfill the task, has obvious bugs, attempts unrelated "
            "file/system operations, or writes outside the specified output directory. "
            "Do not assume that syntax validity proves correctness.\n\n"
            f"TASK:\n{task_description}\n\n"
            + (f"EXACT OUTPUT_DIR (all generated artifacts must stay here):\n{output_dir}\n\n" if output_dir else "")
            + f"CODE:\n```python\n{code}\n```"
        )
        raw = self.generate(
            prompt,
            system_prompt="You are an independent code reviewer. Be strict and evidence-based.",
            max_len=max_len,
        )
        try:
            result = extract_json(raw)
        except (ValueError, json.JSONDecodeError) as exc:
            return {
                "approved": False,
                "issues": [f"Verifier did not return valid JSON: {type(exc).__name__}: {exc}"],
                "summary": "Malformed verifier response; return the required JSON object.",
            }
        if not isinstance(result.get("approved"), bool):
            return {
                "approved": False,
                "issues": ["Verifier JSON is missing a boolean 'approved' field."],
                "summary": "Malformed verifier JSON schema.",
            }
        if not isinstance(result.get("issues", []), list):
            return {
                "approved": False,
                "issues": ["Verifier JSON field 'issues' must be an array."],
                "summary": "Malformed verifier JSON schema.",
            }
        if not isinstance(result.get("summary", ""), str):
            return {
                "approved": False,
                "issues": ["Verifier JSON field 'summary' must be a string."],
                "summary": "Malformed verifier JSON schema.",
            }
        return result


def summarize_dataset(raw_data):
    # Build a compact schema and sample report without sending the full dataset to the model.
    keys = sorted({str(key) for item in raw_data for key in item.keys()})
    type_summary = {}
    for key in keys:
        observed = {type(item.get(key)).__name__ for item in raw_data if key in item}
        type_summary[key] = sorted(observed)
    return {
        "rows": len(raw_data),
        "keys": keys,
        "value_types": type_summary,
        "sample_rows": raw_data[:3],
    }


class LMLPipeline:
    def __init__(
        self,
        generator_path,
        verifier_path,
        dataset_path,
        save_dir,
        max_length=512,
        persona_content="",
        persona_path=None,
    ):
        self.generator_path = os.path.abspath(generator_path)
        self.verifier_path = os.path.abspath(verifier_path)
        self.dataset_path = os.path.abspath(dataset_path)
        self.save_dir = os.path.abspath(save_dir)
        self.max_length = max_length
        self.persona_content = persona_content.strip()
        self.persona_path = persona_path
        if not self.persona_content:
            raise ValueError("A non-empty lml_persona.md is required to run the pipeline.")

    def _get_hardware_context(self):
        """Collect basic hardware facts without requiring extra packages."""
        context = {
            "device": lml_config.DEVICE,
            "gpu_name": None,
            "gpu_memory_gib": None,
            "system_ram_gib": None,
        }
        try:
            if lml_config.DEVICE == "cuda" and torch.cuda.is_available():
                props = torch.cuda.get_device_properties(0)
                context["gpu_name"] = props.name
                context["gpu_memory_gib"] = round(props.total_memory / (1024 ** 3), 2)
        except Exception as exc:
            context["gpu_probe_note"] = str(exc)
        # Linux/macOS: use sysconf. Windows: query total physical memory via
        # the built-in Win32 API so no additional Python package is required.
        try:
            if hasattr(os, "sysconf"):
                pages = os.sysconf("SC_PHYS_PAGES")
                page_size = os.sysconf("SC_PAGE_SIZE")
                context["system_ram_gib"] = round(pages * page_size / (1024 ** 3), 2)
            elif sys.platform == "win32":
                import ctypes
                from ctypes import wintypes

                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ("dwLength", wintypes.DWORD),
                        ("dwMemoryLoad", wintypes.DWORD),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                    ]

                memory_status = MEMORYSTATUSEX()
                memory_status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory_status)):
                    context["system_ram_gib"] = round(
                        memory_status.ullTotalPhys / (1024 ** 3), 2
                    )
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        return context

    def _interactive_training_settings(self, generator, report):
        """Ask FTLLM for a sizing recommendation, then collect user precision choice."""
        hardware = self._get_hardware_context()
        prompt = (
            "Estimate a reasonable target language-model parameter size for this dataset "
            "and hardware. Return ONLY JSON with keys "
            '"recommended_parameters_b" (positive number), "reason" (string), '
            '"cautions" (array of strings). Be conservative; do not claim benchmarking.\n'
            "HARDWARE:\n" + json.dumps(hardware, ensure_ascii=False)
            + "\nDATASET REPORT:\n" + json.dumps(report, ensure_ascii=False)
        )
        recommendation = extract_json(generator.generate(
            prompt,
            system_prompt=self._generator_system_prompt(
                "Recommend conservatively. Output valid JSON only."
            ),
            max_len=500,
        ))
        suggested = recommendation.get("recommended_parameters_b")
        if isinstance(suggested, bool) or not isinstance(suggested, (int, float)) or suggested <= 0:
            raise ValueError("FTLLM returned an invalid recommended_parameters_b value.")

        print("\n" + "=" * 56)
        print(" LML INTERACTIVE MODEL SETTINGS")
        print("=" * 56)
        print(f"FTLLM recommendation: {suggested:g}B parameters")
        print(f"Reason: {recommendation.get('reason', 'No reason provided.')}")
        for caution in recommendation.get("cautions", []):
            print(f" - {caution}")
        print(
            "\nNote: this pipeline fine-tunes the existing --ftllm model. "
            "The target size is a planning preference and does NOT resize or rebuild "
            "the loaded base model."
        )

        choices = {"1": "auto", "2": "fp32", "3": "fp16", "4": "bf16"}
        default = "3" if hardware["device"] == "cuda" else "1"
        if sys.stdin is not None and sys.stdin.isatty():
            answer = input(
                f"Target parameter size in billions [Enter = {suggested:g}]: "
            ).strip()
            try:
                target_size = float(answer) if answer else float(suggested)
            except ValueError as exc:
                raise ValueError("Target parameter size must be numeric.") from exc

            print("\nSelect training precision:")
            print("  1) auto  - choose a supported mode")
            print("  2) fp32  - full precision")
            print("  3) fp16  - half precision")
            print("  4) bf16  - bfloat16 (requires hardware support)")
            selected = input(f"Precision [1-4, Enter = {default}]: ").strip() or default
        else:
            # Non-interactive runs use the FTLLM size suggestion and safe automatic precision.
            target_size = float(suggested)
            selected = "1"
            print(
                "[i] No interactive TTY detected; using FTLLM's suggested target size "
                f"({target_size:g}B) and automatic precision."
            )

        if not 0 < target_size <= 10000:
            raise ValueError("Target parameter size must be greater than 0 and at most 10000.")
        if selected not in choices:
            raise ValueError("Precision must be selected from 1, 2, 3, or 4.")

        settings = {
            "target_parameters_b": target_size,
            "precision": choices[selected],
            "hardware": hardware,
            "ftllm_recommendation": recommendation,
        }
        print(f"[i] Selected target: {target_size:g}B | precision: {choices[selected]}")
        return settings

    def _write_json(self, path, payload):
        with open(path, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")

    def _run_generated_script(self, script_path, stage_dir):
        # Execute generated scripts after static checks; this is not a security sandbox.
        env = os.environ.copy()
        env.update({
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_DATASETS_OFFLINE": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1",
        })
        output_tail = []
        process = subprocess.Popen(
            [sys.executable, str(script_path)],
            cwd=stage_dir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="", flush=True)
            output_tail.append(line.rstrip())
            if len(output_tail) > 100:
                output_tail.pop(0)
        return_code = process.wait()
        if return_code != 0:
            tail = "\n".join(output_tail)[-8000:]
            raise RuntimeError(
                f"Generated script failed with exit code {return_code}:\n{tail}"
            )

    def _generator_system_prompt(self, task_specific):
        # The user's lml_persona.md is mandatory and is the system identity for FTLLM.
        # Do not silently fall back to a generic system prompt.
        if not self.persona_content.strip():
            raise RuntimeError("FTLLM blocked: required lml_persona.md is missing or empty.")
        return (
            "=== REQUIRED LML PERSONA (lml_persona.md) ===\n"
            + self.persona_content.strip()
            + "\n=== END LML PERSONA ===\n\n"
            + "LML execution requirements:\n"
            + "Follow the persona's role, operating guidelines, and structured-output contract. "
            + "Use supplied dataset and hardware facts only; never claim measurements that were "
            + "not actually provided.\n\n"
            + task_specific
        )

    def _generate_and_review(self, generator, verifier, code_prompt, system_prompt,
                             task_description, code_path, review_path, allowed_imports,
                             max_tokens, output_dir=None, max_revisions=2):
        # One initial generation plus up to max_revisions feedback-driven rewrites.
        if max_revisions < 0:
            raise ValueError("max_revisions must be zero or greater.")

        current_prompt = code_prompt
        last_review = None

        for attempt in range(max_revisions + 1):
            if generator.model is None:
                generator.load_model()
            code = extract_code(generator.generate(
                current_prompt, system_prompt=system_prompt, max_len=max_tokens
            ))
            generator.unload_model()

            if not code.strip():
                review = {
                    "approved": False,
                    "issues": ["The generated response was empty or contained no Python code."],
                    "summary": "Empty code response.",
                }
            else:
                try:
                    validate_generated_python(code, allowed_imports)
                except Exception as exc:
                    # Static-check failures are fed back to FTLLM instead of aborting the pipeline.
                    review = {
                        "approved": False,
                        "issues": [f"Static validation failed: {type(exc).__name__}: {exc}"],
                        "summary": "Generated code did not pass the static validation policy.",
                    }
                else:
                    code_path.write_text(code + "\n", encoding="utf-8")
                    verifier.load_model()
                    try:
                        review = verifier.verify_code(
                            code, task_description, output_dir=output_dir
                        )
                    finally:
                        verifier.unload_model()

            self._write_json(review_path, review)
            if review.get("approved") is True:
                if attempt:
                    print(
                        f"[+] Code approved for {code_path.name} after {attempt} rewrite(s)."
                    )
                return code, review

            last_review = review
            if attempt >= max_revisions:
                break

            issues = review.get("issues", [])
            summary = review.get("summary", "")
            print(
                f"[!] {code_path.name} rejected (attempt {attempt + 1}/{max_revisions + 1}). "
                f"Requesting rewrite {attempt + 1}/{max_revisions}..."
            )
            current_prompt = (
                code_prompt
                + "\n\nVALIDATION / VERIFIER FEEDBACK — PREVIOUS CODE WAS REJECTED.\n"
                + "Rewrite the complete script to fix every issue below. Do not merely explain. "
                + "Return full corrected Python code only.\n"
                + f"SUMMARY:\n{summary}\n\nISSUES:\n"
                + json.dumps(issues, ensure_ascii=False, indent=2)
                + "\n\nPREVIOUS GENERATED CODE:\n```python\n"
                + code
                + "\n```\nPreserve all original task requirements and exact paths/constants. "
                + "Do not introduce imports outside the allowed policy."
            )

        raise RuntimeError(
            f"Code generation for {code_path.name} failed after "
            f"{max_revisions + 1} attempt(s). See {review_path}. "
            f"Last summary: {last_review.get('summary', '') if last_review else 'N/A'}"
        )

    def run(self, raw_data):
        # Define all durable artifacts under --save_dir.
        os.makedirs(self.save_dir, exist_ok=True)
        save_path = Path(self.save_dir)
        work_dir = save_path / "work"
        code_dir = save_path / "code"
        review_dir = save_path / "verification"
        tokenizer_dir = save_path / "tokenizer"
        checkpoint_dir = save_path / "checkpoints"
        for directory in (work_dir, code_dir, review_dir, tokenizer_dir, checkpoint_dir):
            directory.mkdir(parents=True, exist_ok=True)

        if self.persona_path and os.path.isfile(self.persona_path):
            shutil.copy2(self.persona_path, save_path / "persona_used.md")
        else:
            (save_path / "persona_used.md").write_text(
                self.persona_content + "\n", encoding="utf-8"
            )

        cleaned_dataset_path = save_path / "dataset_cleaned.jsonl"
        cleaned_data = write_cleaned_jsonl(raw_data, str(cleaned_dataset_path))
        report = summarize_dataset(cleaned_data)
        report["source_dataset"] = self.dataset_path
        report["cleaned_dataset"] = str(cleaned_dataset_path)
        report["replacement_characters_removed"] = True
        report_path = save_path / "dataset_analysis.json"
        self._write_json(report_path, report)

        generator = LMLCore(self.generator_path, role="generator")
        verifier = LMLCore(self.verifier_path, role="verifier")
        try:
            generator.load_model()
            # Ask the generator to apply the persona and return a machine-readable plan.
            analysis_prompt = (
                "Analyze the supplied JSONL dataset report. Return ONLY one JSON object with keys: "
                '"dataset_quality" (string), "curriculum" (array with Foundation, Application, Practical '
                "stages), \"tokenizer_recommendations\" (array of strings), "
                '"training_recommendations" (array of strings), and "risks" (array of strings). '
                "Base conclusions only on the report; do not invent dataset properties.\n\nREPORT:\n"
                + json.dumps(report, ensure_ascii=False)
            )
            analysis_raw = generator.generate(
                analysis_prompt,
                system_prompt=self._generator_system_prompt(
                    "For analysis requests, output valid JSON only, with no Markdown fences."
                ),
                max_len=1400,
            )
            analysis = extract_json(analysis_raw)
            expected_keys = {
                "dataset_quality", "curriculum", "tokenizer_recommendations",
                "training_recommendations", "risks",
            }
            missing_keys = sorted(expected_keys - set(analysis))
            if missing_keys:
                raise ValueError(
                    "Generator analysis response is missing required keys: " + ", ".join(missing_keys)
                )
            self._write_json(save_path / "ai_dataset_analysis.json", analysis)
            training_settings = self._interactive_training_settings(generator, report)
            self._write_json(save_path / "training_settings.json", training_settings)
            generator.unload_model()

            generator.load_model()
            tokenizer_prompt = (
                "Write a complete, runnable Python script that trains a BPE tokenizer using "
                "the `tokenizers` library from the cleaned JSONL dataset. Read DATASET_PATH line by line; "
                "train on textual values from every row, including nested string values where practical. "
                "Write tokenizer.json, tokenizer_config.json, and special_tokens_map.json under OUTPUT_DIR. "
                "Use `transformers.PreTrainedTokenizerFast` to save a Hugging Face-compatible tokenizer. "
                "Use vocabulary size 32000 unless the dataset report supports a smaller size. "
                "Do not download anything, use network access, subprocesses, or write outside OUTPUT_DIR. "
                "Define DATASET_PATH and OUTPUT_DIR constants with exactly these values: "
                f"DATASET_PATH={str(cleaned_dataset_path)!r}, OUTPUT_DIR={str(tokenizer_dir)!r}. "
                "Return Python code only.\n\nDATASET REPORT:\n"
                + json.dumps(report, ensure_ascii=False)
                + "\n\nAI ANALYSIS:\n"
                + json.dumps(analysis, ensure_ascii=False)
            )
            tokenizer_code, _ = self._generate_and_review(
                generator=generator,
                verifier=verifier,
                code_prompt=tokenizer_prompt,
                system_prompt=self._generator_system_prompt(
                    "For code-generation requests, output complete executable Python code only. "
                    "Do not omit imports, constants, error handling, or required save operations."
                ),
                task_description=(
                    "Train a tokenizer from dataset_cleaned.jsonl and save a usable Hugging Face fast "
                    f"tokenizer under this exact OUTPUT_DIR: {str(tokenizer_dir)}. "
                    "Write no files outside that directory."
                ),
                code_path=code_dir / "generated_tokenizer.py",
                review_path=review_dir / "tokenizer_review.json",
                allowed_imports={"json", "os", "pathlib", "tokenizers", "transformers"},
                max_tokens=2400,
                output_dir=tokenizer_dir,
            )
            generator.unload_model()
            print("[i] Verifier approved tokenizer code. Starting tokenizer stage...")
            self._run_generated_script(code_dir / "generated_tokenizer.py", str(work_dir))
            if not (tokenizer_dir / "tokenizer.json").is_file():
                raise RuntimeError(
                    "Tokenizer stage finished without tokenizer/tokenizer.json. "
                    "Check code/generated_tokenizer.py and its output."
                )

            generator.load_model()
            training_output_dir = checkpoint_dir / "final_model"
            training_prompt = (
                "Write a complete Python training script for causal language-model fine-tuning using "
                "Hugging Face Transformers Trainer. Read the cleaned JSONL at DATASET_PATH. Load the "
                "local base/factory model from MODEL_PATH with local_files_only=True and "
                "torch_dtype=torch.float32 (keep model weights in fp32; use Trainer mixed-precision "
                "autocast for fp16/bf16 rather than loading fp16 weights), and load the newly "
                "generated tokenizer from TOKENIZER_PATH with AutoTokenizer.from_pretrained. Before training, "
                "compare len(tokenizer) with model.get_input_embeddings().num_embeddings. If they differ, "
                "call model.resize_token_embeddings(len(tokenizer)) and update model.config.vocab_size; "
                "if the model architecture does not support resizing, stop with a clear error instead of "
                "silently training with mismatched vocabulary dimensions. Verify tokenizer special-token IDs "
                "are within the resized vocabulary. Extract useful text from each row: prefer "
                "instruction/input/output/text/content fields when present; "
                "otherwise combine non-empty string fields. Tokenize with truncation and MAX_LENGTH. "
                "Use per-device batch size 1, gradient accumulation 4, one epoch, report_to='none', "
                "save_strategy='epoch', and save the final model and tokenizer to OUTPUT_DIR. Trainer "
                "checkpoints must also be inside OUTPUT_DIR. Apply selected precision "
                f"{training_settings['precision']}: fp16=True/bf16=False for fp16; "
                "bf16=True/fp16=False for bf16; both False for fp32. For auto, choose a supported mode "
                "conservatively and never enable unsupported precision. The requested target model size is "
                f"{training_settings['target_parameters_b']:g}B, but MODEL_PATH is an existing base model: "
                "do not claim this changes its parameter count or rebuilds its architecture. "
                "Report any mismatch between requested and loaded model size. Do not download anything, "
                "use network access, subprocesses, or write outside OUTPUT_DIR. Define DATASET_PATH, "
                "MODEL_PATH, TOKENIZER_PATH, OUTPUT_DIR, and MAX_LENGTH with exactly these values: "
                f"DATASET_PATH={str(cleaned_dataset_path)!r}, MODEL_PATH={self.generator_path!r}, "
                f"TOKENIZER_PATH={str(tokenizer_dir)!r}, OUTPUT_DIR={str(training_output_dir)!r}, "
                f"MAX_LENGTH={self.max_length}. Return Python code only.\n\nTRAINING SETTINGS:\n"
                + json.dumps(training_settings, ensure_ascii=False)
                + "\n\nDATASET REPORT:\n"
                + json.dumps(report, ensure_ascii=False)
                + "\n\nAI ANALYSIS:\n"
                + json.dumps(analysis, ensure_ascii=False)
            )

            training_code, _ = self._generate_and_review(
                generator=generator,
                verifier=verifier,
                code_prompt=training_prompt,
                system_prompt=self._generator_system_prompt(
                    "For code-generation requests, output complete executable Python code only. "
                    "Ensure the tokenizer and output paths exactly match the supplied constants."
                ),
                task_description=(
                    "Fine-tune the local causal language model on the cleaned JSONL dataset using the "
                    "generated tokenizer. Before training, verify tokenizer vocabulary size against the "
                    "model input embeddings and resize embeddings when required and supported. The exact "
                    f"final model/checkpoint OUTPUT_DIR is {str(training_output_dir)}. Save final weights "
                    "and Trainer checkpoints there, "
                    "without network access or writes outside that directory. Load model weights in "
                    "fp32 and use Trainer mixed precision for the selected precision."
                ),
                code_path=code_dir / "generated_training.py",
                review_path=review_dir / "training_review.json",
                allowed_imports={"json", "os", "pathlib", "torch", "datasets", "transformers", "tokenizers"},
                max_tokens=3000,
                output_dir=training_output_dir,
            )
            generator.unload_model()
            print("[i] Verifier approved training code. Starting training stage...")
            self._run_generated_script(code_dir / "generated_training.py", str(work_dir))
            if not training_output_dir.is_dir():
                raise RuntimeError(
                    f"Training script completed but final model directory was not created: {training_output_dir}"
                )
            print(f"[i] Pipeline completed. Artifacts saved under: {self.save_dir}")
        finally:
            generator.unload_model()
            verifier.unload_model()
