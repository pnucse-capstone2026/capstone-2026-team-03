# Git 업로드 제외 정책

대상 저장소: `pnucse-capstone2026/capstone-2026-team-03`

이 문서는 프로젝트를 캡스톤 모노레포에서 관리할 때 포함할 파일과 로컬에만 둘 파일의 기준을 기록한다.

## 기본 원칙

- 직접 작성한 소스 코드, 테스트, 설정 예시, 의존성 명세와 잠금 파일은 커밋한다.
- 비밀번호나 토큰이 들어갈 수 있는 실제 환경 파일은 커밋하지 않는다.
- 다시 다운로드하거나 재생성할 수 있는 의존성, 모델, 캐시와 빌드 결과는 커밋하지 않는다.
- 용량이 큰 원본 음성 데이터, 전처리 특징, 체크포인트와 실험 로그는 Git이 아닌 별도 저장소에서 관리한다.
- 출처나 재배포 권한이 불명확한 데이터는 권리를 확인하기 전까지 커밋하지 않는다.

## 현재 제외한 주요 항목

| 경로 또는 유형 | 확인된 규모/예시 | 제외 이유 | 복구 방법 |
| --- | ---: | --- | --- |
| `Jipangi/**/.env`, `*.pem`, `*.key` 등 | 로컬 설정 | 비밀정보 유출 방지 | `.env.example`을 복사한 뒤 로컬 값 입력 |
| `node_modules/`, `.venv*/`, Python/Expo 캐시 | `Jipangi` 전체에서 다수 확인 | 설치 및 실행 시 재생성 가능 | 잠금 파일 또는 requirements로 재설치 |
| `judge_models/` | 약 17GB | 외부에서 받은 LLM 가중치 | 원본 모델 배포처에서 다시 다운로드 |
| `qwen/` | 약 5.7GB | 외부에서 받은 LLM 가중치 | 원본 모델 배포처에서 다시 다운로드 |
| `.hf_cache/`, `Jipangi/backend/models/` | Whisper 캐시 파일 포함 | 다운로드 캐시이며 GitHub 용량 제한에 부적합 | 애플리케이션 초기화 과정에서 다시 다운로드 |
| `processed_data/` | 약 65GB | 전처리한 음성 데이터 | 원본 데이터로 전처리 스크립트 재실행 |
| `allosaurus/workspace/` | 10GB 및 32GB `feat.ark` 확인 | 학습 특징과 실행 워크스페이스 | 학습/전처리 스크립트 재실행 |
| `allosaurus/한국전자통신연구원_*` | 원본 음성 데이터 | 대용량이며 재배포 권한 확인 필요 | 승인된 원본 데이터 위치에서 관리 |
| `allosaurus/{wandb,reports,runs,outputs,...}` | 실험별 생성물 | 실행 시 재생성 가능 | 해당 실험을 다시 실행 |
| `Jipangi/tools/cloudflared` | 약 38MB | 플랫폼별 다운로드 실행 파일 | 공식 배포처에서 다시 설치 |
| SQLite, Django media/staticfiles, 로그 | 런타임 생성물 | 개발 환경별 상태이며 재생성 가능 | 마이그레이션 및 실행 과정에서 생성 |
| 최상위 `korean_*.json`, `korean_*.xlsx` | 로컬 문장 데이터 | 출처·재배포 권한 확인 전에는 코드와 분리 | 권한 확인 후 별도 데이터 관리 정책에 따라 추가 |

## 의도적으로 포함하는 항목

- `Jipangi/`의 애플리케이션 소스, 마이그레이션, 테스트와 문서
- `allosaurus/`의 수정한 라이브러리 소스, 설정, 스크립트와 테스트
- `requirements.txt`, `package.json`, `package-lock.json`, `environment.yml`
- 실제 값이 없는 `.env.example`
- `report/`의 LaTeX 원본과 이미지 자산
- `allosaurus/sample.wav`: 약 17KB의 실행 예제 파일

## 저장소 구조

캡스톤 저장소는 `Jipangi/`와 `allosaurus/`의 소스 스냅샷을 일반 디렉터리로 포함하는 모노레포다. 기존 두 저장소의 `.git/` 메타데이터는 복사하지 않았으므로 중첩 저장소나 서브모듈로 취급되지 않는다.

원본 작업 디렉터리의 하위 Git 이력은 그대로 보존한다. 이후 소스를 갱신할 때도 하위 `.git/`을 캡스톤 저장소에 복사하지 않는다.

## 업로드 전 점검 명령

커밋하거나 푸시하기 전에 다음을 확인한다.

```bash
git status --short --ignored
git check-ignore -v Jipangi/backend/.env
git check-ignore -v Jipangi/frontend/node_modules
git check-ignore -v judge_models/EXAONE-3.5-2.4B-Instruct/model-00001-of-00002.safetensors
find . -type f -size +50M -not -path '*/.git/*'
```

마지막 명령에 표시되는 파일은 모두 업로드 필요성과 라이선스를 다시 검토한다. `.gitignore`는 이미 Git이 추적 중인 파일에는 적용되지 않으므로, 기존 저장소에서 추적 중인 파일을 제외하려면 별도의 인덱스 정리가 필요하다.
