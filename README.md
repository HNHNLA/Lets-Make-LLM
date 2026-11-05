# LML (Let's Make LLM) - Alpha v1.0.0
[한국어로 보기](#lml-lets-make-llm---알파-v100)

> A meta-AI engine where a base model acts as an architect to design and build new model structures.

**Alpha Stage & Notice**:
LML is an early **alpha**. The full pipeline (analysis → code generation → verification → training) is implemented, but it has not been broadly validated. Results depend heavily on the generator and verifier models you choose, and the generated code is executed on your machine **without a sandbox**. Please read the *Limitations & Safety* section below before running it.

---

## How It Works

1. **Load & clean the dataset** – reads a JSONL file (one JSON object per line), drops invalid UTF-8 bytes, removes U+FFFD replacement characters, and saves `dataset_cleaned.jsonl`.
2. **Analyze** – builds a dataset report and detects your hardware (NVIDIA CUDA, AMD ROCm, Intel XPU, or CPU). The generator model (`--ftllm`) adds its own analysis.
3. **Choose settings** – interactively confirm the recommended target model size and select a training precision.
4. **Tokenizer** – the generator writes tokenizer-training code → AST safety check → verifier review (rewritten on rejection) → the script runs and saves the tokenizer.
5. **Training** – the generator writes hardware-aware training code → the same checks → the script runs and saves the final model.

## Features in v1.0.0-alpha

* **AI-based tokenizer design and code generation**: analyzes the dataset and generates tokenizer-training code suited to it.
* **Hardware-aware training code generation**: generates training code based on the detected hardware and the selected precision.
* **Independent AI code cross-verification**: a separate verifier model (`--verifier-llm`) reviews every generated script. Rejected code is sent back to the generator for up to 2 rewrites.
* **AST static safety check**: an allowlist-based check runs before the verifier. It rejects dangerous imports, calls, and escape patterns. It is a first filter, **not** a sandbox.
* **Interactive parameter recommendation**: the generator suggests a target model size, which you can confirm or change. *(Advisory only, see Limitations.)*
* **Precision selection**: `auto`, `fp32`, `fp16`, or `bf16`. Non-interactive runs use the suggested size and `auto`.
* **End-to-end training**: runs the generated training script and saves the final model under `--save_dir`.
* **Version command**: `lml --version`.
* **Editable installation**: `pip install -e .`.

## Requirements

* Python 3.10 or newer
* `transformers>=4.40.0`, `torch`, `datasets`, `accelerate`, `tokenizers` (installed automatically by pip)
* Two **local** model directories: a generator (`--ftllm`) and a separate verifier (`--verifier-llm`)
* A GPU is optional but strongly recommended

## Installation

### Option A: pip (Linux / macOS / Windows)

```bash
git clone https://github.com/HNHNLA/Lets-Make-LLM.git
cd Lets-Make-LLM
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -e .
lml --version
```

If you need a specific CUDA or ROCm build of PyTorch, install it from [pytorch.org](https://pytorch.org) first, then run `pip install -e .`.

### Option B: Debian / Ubuntu (.deb)

```bash
git clone https://github.com/HNHNLA/Lets-Make-LLM.git
cd Lets-Make-LLM
bash build_deb.sh
cd build
sudo apt install ./lml_1.0.0~alpha_all.deb
```

The package depends on Python 3.10+ but **does not install** PyTorch or the other Python packages. Point the launcher at a Python environment that has them:

```bash
LML_PYTHON=/path/to/venv/bin/python lml --version
```

Uninstall:

```bash
sudo apt purge lml
```

### Option C: Windows installer

Pre-compiled `.exe` binaries are not included. On Windows, use Option A. An Inno Setup script (`setup.iss`) is provided for anyone who wants to build an installer; this path is **experimental and untested** for this release. It expects `dist\lml\lml.exe`:

```cmd
pip install pyinstaller
pyinstaller --onefile --name lml --distpath dist/lml lml_engine.py
```

Bundling PyTorch with PyInstaller may require additional options.

## Usage

```bash
lml --dataset ./data/train.jsonl \
    --ftllm ./models/generator \
    --verifier-llm ./models/verifier \
    --save_dir ./lml_output \
    --max-length 512 \
    --logging ./logs
```

| Argument         | Required | Description                                                   |
| ---------------- | -------- | ------------------------------------------------------------- |
| `--dataset`      | yes      | Path to the JSONL training dataset (one JSON object per line) |
| `--ftllm`        | yes      | Local directory of the generator ("factory") model            |
| `--verifier-llm` | yes      | Local directory of a separate code-review model               |
| `--save_dir`     | yes      | Directory for generated artifacts and the trained model       |
| `--max-length`   | yes      | Maximum token sequence length (at least 8)                    |
| `--logging`      | no       | Directory for log files                                       |
| `--version`      | –        | Print the version and exit                                    |

`lml help` prints a short usage summary.

### Output layout

```
lml_output/
├── persona_used.md            # persona used for this run
├── dataset_cleaned.jsonl
├── dataset_analysis.json
├── ai_dataset_analysis.json
├── training_settings.json
├── code/
│   ├── generated_tokenizer.py
│   └── generated_training.py
├── verification/
│   ├── tokenizer_review.json
│   └── training_review.json
├── tokenizer/
├── checkpoints/
│   └── final_model/
└── work/                      # scratch space
```

## Limitations & Safety

* **No sandbox.** Approved code runs as a subprocess with *your* user permissions. The AST check is a first filter and the verifier is an LLM that can be wrong. Use datasets you trust (dataset samples are placed into prompts), and run LML in a VM or container when possible.
* **Quality depends on your models.** Use a generator that writes reliable Python and a verifier that follows the requested JSON format. Smaller models fail more often. Results are not guaranteed.
* **The target model size is advisory.** LML fine-tunes the existing base model; it does not resize or redesign its architecture.
* **Tokenizer mismatch.** A newly trained tokenizer does not match the base model's original vocabulary. The training script resizes the embeddings when needed, but pretrained embedding knowledge may not carry over, which can reduce quality.
* **Memory.** Weights are kept in fp32 with mixed precision, which needs roughly 16 bytes per parameter for full fine-tuning. Start with a small model (about 1B parameters or less).
* **Dataset encoding.** Invalid UTF-8 bytes are silently dropped. Convert files in other encodings (for example CP949) to UTF-8 first.
* **Offline and unbounded.** Generated scripts run with Hugging Face offline mode enabled, so models must be local directories. There is no time limit on training.

## Project Roadmap

* **v0.1.0-alpha (Core Skeleton Architecture)**: initial project structure, including CLI routing, dataset loading, system logging, and the basic training-pipeline skeleton.
* **v1.0.0-alpha (AI-Assisted Model-Building Pipeline)**: AI-generated tokenizer and training code, independent verifier review, AST safety check, interactive size recommendation and precision selection, `lml --version`, and `pip install -e .`.
* **Possible next steps (not promised)**: sandboxed execution, a dataset damage report, and a Windows installer.

**Note:** The roadmap is subject to change. Features may be added, removed, or modified during development.

---

# LML (Let's Make LLM) - 알파 v1.0.0
[show to english](#lml-lets-make-llm---alpha-v100)

> 기본 모델이 설계자 역할을 맡아 새로운 모델 구조를 설계하고 구축하는 AI 엔진입니다.

**알파 단계 및 안내**:
LML은 초기 **알파** 단계입니다. 전체 파이프라인(분석 → 코드 생성 → 검증 → 학습)은 구현되어 있지만 폭넓게 검증되지는 않았습니다. 결과는 선택한 생성기 모델과 검증자 모델의 성능에 크게 좌우되며, 생성된 코드는 **샌드박스 없이** 사용자의 컴퓨터에서 실행됩니다. 실행 전에 아래의 *제한 사항 및 안전 주의*를 반드시 읽어 주세요.

---

## 동작 방식

1. **데이터셋 로드 및 정리** – JSONL 파일(한 줄에 JSON 객체 하나)을 읽고, 잘못된 UTF-8 바이트를 버리고, U+FFFD 대체 문자를 제거한 뒤 `dataset_cleaned.jsonl`로 저장합니다.
2. **분석** – 데이터셋 리포트를 만들고 하드웨어(NVIDIA CUDA, AMD ROCm, Intel XPU, CPU)를 감지합니다. 생성기 모델(`--ftllm`)이 자체 분석을 추가합니다.
3. **설정 선택** – 추천 목표 모델 크기를 대화형으로 확인하고 학습 정밀도를 선택합니다.
4. **토크나이저** – 생성기가 토크나이저 학습 코드를 작성 → AST 안전 검사 → 검증자 리뷰(거절 시 재작성) → 스크립트 실행 후 토크나이저 저장.
5. **학습** – 생성기가 하드웨어 맞춤 학습 코드를 작성 → 동일한 검사 → 스크립트 실행 후 최종 모델 저장.

## v1.0.0-alpha 기능

* **AI 기반 토크나이저 설계 및 코드 생성**: 데이터셋을 분석해 그에 맞는 토크나이저 학습 코드를 생성합니다.
* **하드웨어 인지형 학습 코드 생성**: 감지된 하드웨어와 선택한 정밀도에 맞는 학습 코드를 생성합니다.
* **독립적인 AI 코드 교차 검증**: 별도의 검증 모델(`--verifier-llm`)이 생성된 모든 스크립트를 검토합니다. 거절된 코드는 생성기에 되돌려 최대 2번까지 다시 작성합니다.
* **AST 정적 안전 검사**: 검증자보다 먼저 허용 목록 기반 검사를 실행해 위험한 import, 호출, 우회 패턴을 거부합니다. 1차 필터이며 샌드박스가 **아닙니다**.
* **대화형 파라미터 추천**: 생성기가 목표 모델 크기를 제안하고, 사용자가 확인하거나 바꿀 수 있습니다. *(참고용입니다. 제한 사항을 확인하세요.)*
* **정밀도 선택**: `auto`, `fp32`, `fp16`, `bf16`. 비대화형 실행은 제안된 크기와 `auto`를 사용합니다.
* **엔드 투 엔드 학습**: 생성된 학습 스크립트를 실행하고 최종 모델을 `--save_dir` 아래에 저장합니다.
* **버전 명령**: `lml --version`.
* **편집 가능한 설치**: `pip install -e .`.

## 요구 사항

* Python 3.10 이상
* `transformers>=4.40.0`, `torch`, `datasets`, `accelerate`, `tokenizers` (pip가 자동 설치)
* **로컬** 모델 디렉터리 두 개: 생성기(`--ftllm`)와 별도의 검증자(`--verifier-llm`)
* GPU는 선택 사항이지만 강력히 권장합니다

## 설치

### 방법 A: pip (Linux / macOS / Windows)

```bash
git clone https://github.com/HNHNLA/Lets-Make-LLM.git
cd Lets-Make-LLM
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -e .
lml --version
```

특정 CUDA 또는 ROCm 빌드의 PyTorch가 필요하면 [pytorch.org](https://pytorch.org)에서 먼저 설치한 뒤 `pip install -e .`를 실행하세요.

### 방법 B: Debian / Ubuntu (.deb)

```bash
git clone https://github.com/HNHNLA/Lets-Make-LLM.git
cd Lets-Make-LLM
bash build_deb.sh
cd build
sudo apt install ./lml_1.0.0~alpha_all.deb
```

이 패키지는 Python 3.10 이상에 의존하지만 PyTorch와 다른 Python 패키지는 **설치해 주지 않습니다**. 필요한 패키지가 설치된 Python 환경을 실행기에 지정하세요.

```bash
LML_PYTHON=/path/to/venv/bin/python lml --version
```

삭제:

```bash
sudo apt purge lml
```

### 방법 C: Windows 설치 프로그램

사전 컴파일된 `.exe` 바이너리는 포함되어 있지 않습니다. Windows에서는 방법 A를 사용하세요. 설치 프로그램을 직접 빌드하려는 경우를 위해 Inno Setup 스크립트(`setup.iss`)가 제공되지만, 이 방법은 이번 릴리스에서 **실험적이며 테스트되지 않았습니다**. 스크립트는 `dist\lml\lml.exe`를 기대합니다:

```cmd
pip install pyinstaller
pyinstaller --onefile --name lml --distpath dist/lml lml_engine.py
```

PyInstaller로 PyTorch를 번들하려면 추가 옵션이 필요할 수 있습니다.

## 사용법

```bash
lml --dataset ./data/train.jsonl \
    --ftllm ./models/generator \
    --verifier-llm ./models/verifier \
    --save_dir ./lml_output \
    --max-length 512 \
    --logging ./logs
```

| 인자 | 필수 | 설명 |
|---|---|---|
| `--dataset` | 예 | JSONL 학습 데이터셋 경로 (한 줄에 JSON 객체 하나) |
| `--ftllm` | 예 | 생성기("공장") 모델의 로컬 디렉터리 |
| `--verifier-llm` | 예 | 별도 코드 리뷰 모델의 로컬 디렉터리 |
| `--save_dir` | 예 | 생성 결과물과 학습된 모델을 저장할 디렉터리 |
| `--max-length` | 예 | 최대 토큰 시퀀스 길이 (8 이상) |
| `--logging` | 아니오 | 로그 파일을 저장할 디렉터리 |
| `--version` | – | 버전을 출력하고 종료 |

`lml help`로 간단한 사용법을 볼 수 있습니다.

### 출력 구조

```
lml_output/
├── persona_used.md            # 이번 실행에 사용한 페르소나
├── dataset_cleaned.jsonl
├── dataset_analysis.json
├── ai_dataset_analysis.json
├── training_settings.json
├── code/
│   ├── generated_tokenizer.py
│   └── generated_training.py
├── verification/
│   ├── tokenizer_review.json
│   └── training_review.json
├── tokenizer/
├── checkpoints/
│   └── final_model/
└── work/                      # 임시 작업 공간
```

## 제한 사항 및 안전 주의

* **샌드박스가 없습니다.** 승인된 코드는 *사용자 권한*으로 서브프로세스에서 실행됩니다. AST 검사는 1차 필터이고 검증자는 틀릴 수 있는 LLM입니다. 신뢰할 수 있는 데이터셋만 사용하고(데이터셋 샘플이 프롬프트에 포함됩니다), 가능하면 VM이나 컨테이너에서 실행하세요.
* **품질은 사용하는 모델에 달려 있습니다.** 파이썬 코드를 안정적으로 쓰는 생성기와 요청한 JSON 형식을 지키는 검증자를 사용하세요. 작은 모델일수록 실패가 잦고, 결과는 보장되지 않습니다.
* **목표 모델 크기는 참고용입니다.** LML은 기존 기본 모델을 파인튜닝하며, 아키텍처를 리사이즈하거나 새로 설계하지 않습니다.
* **토크나이저 불일치.** 새로 학습한 토크나이저는 기본 모델의 원래 어휘와 맞지 않습니다. 학습 스크립트가 필요하면 임베딩을 리사이즈하지만, 사전학습된 임베딩 지식이 이어지지 않아 품질이 떨어질 수 있습니다.
* **메모리.** 가중치를 fp32로 두고 혼합 정밀도를 쓰므로 전체 파인튜닝에는 파라미터당 대략 16바이트가 필요합니다. 작은 모델(약 1B 파라미터 이하)로 시작하세요.
* **데이터셋 인코딩.** 잘못된 UTF-8 바이트는 조용히 버려집니다. 다른 인코딩(예: CP949) 파일은 먼저 UTF-8로 변환하세요.
* **오프라인 및 시간 제한 없음.** 생성된 스크립트는 Hugging Face 오프라인 모드로 실행되므로 모델은 로컬 디렉터리여야 합니다. 학습에는 시간 제한이 없습니다.

## 프로젝트 로드맵

* **v0.1.0-alpha (핵심 골격 아키텍처)**: CLI 라우팅, 데이터셋 로딩, 시스템 로깅, 기본 학습 파이프라인 골격을 포함한 초기 프로젝트 구조.
* **v1.0.0-alpha (AI 지원 모델 구축 파이프라인)**: AI 기반 토크나이저 및 학습 코드 생성, 독립적인 검증자 리뷰, AST 안전 검사, 대화형 크기 추천과 정밀도 선택, `lml --version`, `pip install -e .`.
* **다음 단계 후보 (확정 아님)**: 샌드박스 실행, 데이터셋 손상 리포트, Windows 설치 프로그램.

**참고:** 로드맵은 변경될 수 있습니다. 개발 중 기능이 추가, 제거, 수정될 수 있습니다.
