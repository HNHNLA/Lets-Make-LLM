# LML (Let's Make LLM) - Alpha v0.1.0
[한국어로 보기](#lml-lets-make-llm---알파-v010)

> A meta-AI engine where a base model acts as an architect to design and build new model structures.

**Alpha Stage & Notice**: 
This project is currently in an early **Alpha phase**. Full autonomous training loops are under active development. The project is still under active development, and `pip install -e .` is **not yet supported and may fail** in the current version. Editable-install support is planned for `v1.0.0-alpha`; until then, do not assume that this installation method works.

**Planned Release — v1.0.0-alpha**: The release is currently planned for **November 1–3, 2026**. This is an estimated release window and may change depending on development progress and testing.

* **AMD64 Windows Installer Note**: During a rapid OS migration to a Linux/Ubuntu environment and secure cloud backup (Proton Drive) quota management, legacy pre-compiled `.exe` binaries were omitted to prioritize core source code. However, the Inno Setup script (`setup.iss`) is included in the repository if you still wish to inspect or build it for Windows.

**To build the Windows installer yourself, Python must be installed first. If Python is not installed, download and install it from the [official Python downloads page](https://www.python.org/downloads/windows/). Make sure to enable the `Add Python to PATH` option during installation.**
**After installing Python, use the following commands to install PyInstaller and generate `lml.exe` inside the `dist/lml` directory:**
```cmd
cd C:/Users/Your USERNAME/Downloads/Lets-Make-LLM
pip install pyinstaller
pyinstaller --name lml --distpath dist/lml lml_engine.py
```

### Project Roadmap

*   **v0.1.0-alpha (Core Skeleton Architecture)**: Establishes the initial project structure, including CLI routing, dataset loading, system logging, and the basic training-pipeline skeleton.
*   **v1.0.0-alpha (AI-Assisted Model-Building Pipeline)**:
    *   **AI-Based Tokenizer Design and Code Generation**: Analyze the dataset and generate tokenizer implementation code suited to it.
    *   **Hardware-Aware Training Code Generation**: Generate training code based on the user's hardware specifications.
    *   **Independent AI Code Cross-Verification**: Use a separate verifier model to review the generated code.
    *   **Editable Installation**: Support `pip install -e .`.
    *   **Version Command**: Support `lml --version`.

**Note:** The features listed in the `v1.0.0-alpha` roadmap are subject to change. Additional features may be added, planned features may be removed, and existing features may be modified during development.

---

## Installation (amd64 Ubuntu/Debian)

```bash
sudo apt install ./lml_0.1.0-alpha_amd64.deb
```

## Usage (Example path: C:/users/user/Desktop/example)
```bash
lml --dataset <path> --ftllm <path> --save_dir <path> --logging <path>
```

# LML (Let's Make LLM) - 알파 v0.1.0
[show to english](#lml-lets-make-llm---Alpha-v010)

> 기본 모델이 설계자 역할을 맡아 새로운 모델 구조를 설계하고 구축하는 AI 엔진입니다.

**알파 단계 및 안내**:
이 프로젝트는 현재 초기 **알파 단계**에 있습니다. 완전한 자율 학습 루프는 개발 중이며, 프로젝트는 아직 활발히 개발되고 있습니다. 현재 버전에서는 `pip install -e .` 설치가 아직 지원되지 않으며 현재 상태에서는 실패할 수 있습니다. 편집 가능한 설치 지원은 `v1.0.0-alpha`에서 계획되어 있으며, 그 전까지는 이 설치 방식이 동작한다고 가정하지 마십시오.

**출시 예정 — v1.0.0-alpha**: 현재 **2026년 11월 1일~11월 3일** 출시를 목표로 하고 있습니다. 개발 진행 상황과 테스트 결과에 따라 일정은 변경될 수 있습니다.

* **AMD64 Windows 설치 프로그램 참고 사항**: 빠른 OS 마이그레이션과 Linux/Ubuntu 환경 전환, 그리고 보안 클라우드 백업(Proton Drive) 용량 관리 과정에서 기존 사전 컴파일된 `.exe` 바이너리는 핵심 소스 코드에 우선순위를 두기 위해 제외되었습니다. 그러나 Windows에서 직접 확인하거나 빌드하려면 저장소에 포함된 Inno Setup 스크립트(`setup.iss`)를 사용할 수 있습니다.

**Windows 설치 프로그램을 직접 빌드하려면 먼저 Python이 설치되어 있어야 합니다. Python이 설치되어 있지 않은 경우 [Python 공식 다운로드 페이지](https://www.python.org/downloads/windows/)에서 다운로드하여 설치하십시오. 설치 과정에서 `Add Python to PATH` 옵션을 활성화해야 합니다.**
**Python 설치가 완료되면 다음 명령어를 사용하여 PyInstaller를 설치하고 `dist/lml` 디렉터리에 `lml.exe`를 생성하십시오:**
```cmd
cd C:/Users/Your USERNAME/Downloads/Lets-Make-LLM
pip install pyinstaller
pyinstaller --name lml --distpath dist/lml lml_engine.py
```

### 프로젝트 로드맵

*   **v0.1.0-alpha (핵심 골격 아키텍처)**: CLI 라우팅, 데이터셋 로딩, 시스템 로깅, 기본 학습 파이프라인 골격을 포함한 초기 프로젝트 구조를 확립합니다.
*   **v1.0.0-alpha (AI 지원 모델 구축 파이프라인)**:
    *   **AI 기반 토크나이저 설계 및 코드 생성**: 데이터셋을 분석하여 해당 데이터셋에 적합한 토크나이저 구현 코드를 생성합니다.
    *   **하드웨어 인지형 학습 코드 생성**: 사용자의 하드웨어 사양에 맞는 학습 코드를 생성합니다.
    *   **독립적인 AI 코드 교차 검증**: 별도의 검증 모델을 사용해 생성된 코드를 검토합니다.
    *   **편집 가능한 설치 지원**: `pip install -e .`를 지원합니다.
    *   **버전 명령 지원**: `lml --version`을 지원합니다.

**참고:** `v1.0.0-alpha` 로드맵에 나열된 기능은 변경될 수 있습니다. 추가 기능이 추가될 수 있고, 계획된 기능이 제거될 수도 있으며, 기존 기능도 개발 중에 수정될 수 있습니다.

---

## 설치 (amd64 Ubuntu/Debian)

```bash
sudo apt install ./lml_0.1.0-alpha_amd64.deb
```

## 사용법 (예시 경로: C:/users/user/Desktop/example)
```bash
lml --dataset <path> --ftllm <path> --save_dir <path> --logging <path>
```
