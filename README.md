# 사업자등록증 OCR Lambda API 명세

사업자등록증 이미지/PDF를 OCR 처리해, 사용자가 화면에서 보고 수정할 추정값을 반환하는 Lambda입니다.

**이 Lambda는 OCR과 필드 파싱만 수행합니다.** 사업자등록증 진위 확인, 광고업 판단, 최종 승인 판정, DB 적재는 모두 백엔드 서버가 담당합니다. 서버가 구현해야 할 검증 규칙은 [docs/server-verification-spec.md](docs/server-verification-spec.md)에 있습니다.

**호출자는 프론트가 아니라 백엔드 서버입니다.** 백엔드가 AWS SDK로 직접 invoke하며, API Gateway를 거치지 않습니다. 응답 계약은 백엔드 설계 문서 [`backend/docs/team-creation-api-spec.md`](../backend/docs/team-creation-api-spec.md) 4·8절과 고정되어 있습니다.

## 1. 전체 흐름

```text
로그인
  -> 팀 생성 화면
  -> 프론트가 백엔드 업로드 API에 파일 전송
  -> 백엔드: S3 저장 -> 이 Lambda를 SDK로 invoke -> OCR 결과 수신
  -> 백엔드가 OCR 추정값을 프론트에 응답 (업태·종목은 서명 토큰에 실어 보냄)
  -> 사용자가 추정값 확인/수정
  -> "팀 생성하기" -> 서버가 진위 확인 + 광고업 판단 후 DB 적재
```

| 항목 | 값 |
| --- | --- |
| Lambda Handler | `ocr_service.lambda_handler.handler` |
| Runtime | Python 3.11 또는 Python 3.12 |
| 호출 방식 | **백엔드가 AWS SDK로 직접 invoke** (API Gateway 아님) |
| 입력 파일 위치 | S3 object |
| 지원 파일 | `.jpg`, `.jpeg`, `.png`, `.pdf`, `.tif`, `.tiff` |
| 응답 형식 | **결과 dict 그대로** (proxy 봉투 없음) |
| 동작 | OCR과 파싱만. 외부 검증 없음 |

### 왜 API Gateway를 쓰지 않나

동기 호출에 29초 제한이 걸리고, 인증(JWT authorizer)과 CORS를 따로 관리해야 하며, 인증 없이 열려 있으면 누구나 CLOVA OCR을 호출해 비용을 태울 수 있습니다. 백엔드가 이미 검증한 JWT 세션 안에서 SDK로 부르면 이 문제가 전부 사라집니다. EC2 인스턴스 역할에 `lambda:InvokeFunction`만 추가하면 됩니다.

그래서 **proxy 응답 봉투(`{statusCode, headers, body}`)를 만들지 않습니다.** 결과 dict를 그대로 반환합니다. 이 Lambda를 API Gateway 뒤에 붙이면 동작하지 않습니다.

동작 지정은 요청 본문의 `"action": "ocr"`로 합니다. 그 외 입력은 모두 오류입니다.

**S3 업로드 이벤트로 Lambda를 직접 트리거하는 방식은 지원하지 않습니다.** OCR 결과를 돌려받을 호출자가 없어 결과가 버려지기 때문입니다. `bucket`/`key`만 있고 `action`이 없는 입력을 거부하는 것도 이 오설정을 막기 위해서입니다.

## 2. Request

```json
{
  "action": "ocr",
  "bucket": "loovi-ocr-input",
  "key": "teams/12/business-registration/a1b2.png"
}
```

S3 위치는 아래 형태도 지원합니다.

```json
{ "s3": { "bucket": "loovi-ocr-input", "key": "teams/12/br/a1b2.png" } }
{ "s3Uri": "s3://loovi-ocr-input/teams/12/br/a1b2.png" }
```

S3 객체는 `/tmp`에 내려받지 않고 메모리로 읽습니다. Lambda의 `/tmp`는 warm 컨테이너에서 재사용되어 파일이 쌓이기 때문입니다. 객체 크기는 본문을 읽기 전에 `head_object`로 확인하며, 지원하지 않는 확장자는 S3를 읽기 전에 거절합니다.

추가 요청 옵션:

| 필드 | 예시 | 설명 |
| --- | --- | --- |
| `lang` | `"ko"` | OCR 언어. 기본값 `ko` |
| `timeout` | `60` | Ncloud OCR timeout 초 |

## 3. Response

**proxy 봉투가 없습니다.** 결과 dict를 그대로 반환합니다.

### 성공

백엔드와 고정한 계약은 아래 **6개 필드뿐**입니다. 인식에 실패한 필드는 `null`이지만 **키는 항상 존재합니다** — 백엔드가 키 유무를 확인하지 않고 값만 보면 되도록 하기 위해서입니다.

```json
{
  "companyName": "신한 KLLJS",
  "representativeName": "이정현",
  "businessNumber": "4959240582",
  "businessOpeningDate": "2024-06-24",
  "businessType": "서비스업",
  "businessItem": "광고대행"
}
```

| 필드 | 형식 | 서버 용도 |
| --- | --- | --- |
| `businessNumber` | 숫자 10자리 | 국세청 진위확인 · `business_number` |
| `representativeName` | 문자열 | 국세청 진위확인 · `representative_name` |
| `businessOpeningDate` | `yyyy-MM-dd` | 국세청 진위확인 · `business_opening_date` |
| `companyName` | 문자열 | `company_name` (검증 대상 아님) |
| `businessType` (업태) | 문자열 | **광고업 판단** (검증 대상 아님) |
| `businessItem` (종목) | 문자열 | **광고업 판단** (검증 대상 아님) |

`businessNumber`가 10자리로, `businessOpeningDate`가 8자리 날짜로 정규화되지 않으면 그 값은 `null`입니다 — 서버가 그대로 국세청에 보낼 수 없는 값이기 때문입니다. 사용자가 화면에서 직접 입력하게 됩니다.

**업태·종목은 특별합니다.** 광고업 판단의 유일한 입력인데 국세청이 확인해주지 않습니다. 그래서 백엔드는 이 두 값을 사용자에게 보여주지 않고 **서명 토큰(`documentStorageKey`)에 실어 나릅니다** — 폼으로 받으면 실제로는 음식점업인 사람이 "광고대행"으로 고쳐 제출해 스스로를 승인시킬 수 있기 때문입니다. **이 두 필드의 인식률이 OCR 품질의 핵심 지표입니다** (못 읽으면 팀 생성이 막힙니다).

**사업장주소는 응답에 넣지 않습니다.** DB에 저장하지도, 검증에 쓰지도 않는 개인정보이기 때문입니다. 필수 필드에서도 빠졌으므로 주소를 읽지 못했다는 이유로 보조 OCR을 다시 호출하지 않습니다.

응답에는 `advertisingClassification`, `verification`, `eligibility` 같은 판정 결과가 없습니다. 그 계산은 서버가 합니다. 파서 경고(`warnings`)도 응답 계약에 넣지 않고 **CloudWatch 로그로만** 남깁니다 — 백엔드가 쓰지 않는 값으로 계약을 늘릴 이유가 없습니다.

OCR 응답은 **사용자가 수정하기 전의 추정값**입니다. 서버는 사용자가 확정한 값을 기준으로 검증합니다(업태·종목만 예외 — 위 참고).

## 4. Error Response

실패해도 **예외를 던지지 않고** 아래 형태를 반환합니다.

```json
{
  "error": "ExternalServiceError",
  "message": "Ncloud OCR request failed: ... (X-OCR-SECRET: ***REDACTED***)"
}
```

백엔드는 이 응답을 받으면 **OCR 필드를 전부 `null`로 채우고 업로드는 성공으로 처리합니다.** OCR 실패가 사용자 흐름을 막으면 안 되기 때문입니다 — 사용자가 값을 직접 입력하면 됩니다. 그래서 여기서 예외를 던져 호출자를 실패시키는 것보다, 파싱하기 쉬운 형태로 돌려주고 원인은 CloudWatch에 남기는 편이 낫습니다.

외부 API 호출이 실패하면 `ExternalServiceError`로 감쌉니다. 원본 예외 메시지에는 요청 URL과 시크릿이 섞일 수 있으므로, **응답과 CloudWatch 로그 어느 쪽으로도 나가기 전에** 비밀값을 `***REDACTED***`로 가립니다.

| `error` / 증상 | 확인할 것 |
| --- | --- |
| `operation must be 'ocr'` | 요청에 `"action": "ocr"`이 있는지. S3 이벤트 트리거로 잘못 연결됐는지 |
| `Missing S3 object location` | `bucket`/`key`가 있는지 |
| `Bucket is not allowed for OCR input` | `OCR_INPUT_BUCKET`과 요청 버킷이 같은지 |
| `Unsupported file format` | 지원 확장자 여부 (백엔드가 먼저 걸러야 정상) |
| `File is too large for OCR request` | 파일 크기와 `NCLOUD_OCR_MAX_FILE_BYTES` |
| `ExternalServiceError` | Lambda timeout, VPC NAT, outbound 보안 그룹, Ncloud 장애 |
| `AccessDenied` | Lambda role의 `s3:GetObject` 권한 |
| `Missing required environment variable` | 필수 환경 변수 설정 |

## 5. 호출자 보안

**객체 키 조작.** 호출자가 준 `bucket`/`key`를 그대로 믿으면, Lambda role이 읽을 수 있는 모든 객체를 OCR에 태워 내용을 볼 수 있습니다. `OCR_INPUT_BUCKET`으로 허용 버킷을 못박으면 다른 버킷은 막히지만 **같은 버킷 안의 다른 팀 문서는 막지 못합니다.**

지금 구조에서는 이 문제가 사라집니다 — **호출자가 백엔드 서버뿐이고, 키를 정하는 주체도 백엔드**이기 때문입니다. 백엔드는 `team-registrations/{uuid}` 형태의 추측 불가능한 키를 스스로 만들어 S3에 올린 뒤 그 키로 Lambda를 부릅니다. 브라우저는 이 키를 볼 수도 바꿀 수도 없습니다(백엔드가 HMAC 서명 토큰으로 감싸 프론트에 넘깁니다).

**인증.** API Gateway를 열어두면 누구나 CLOVA OCR을 호출해 비용을 태울 수 있습니다. 이 Lambda는 API Gateway 뒤에 두지 않습니다 — 백엔드가 이미 검증한 JWT 세션 안에서 SDK로만 호출합니다. `OCR_INPUT_BUCKET`은 그래도 설정해 두세요(다층 방어).

## 6. Deployment Spec

패키지 생성:

```powershell
.\scripts\package_lambda.ps1
```

생성 파일:

```text
dist\lambda-deploy.zip
```

기존에 검증된 Linux 의존성 ZIP을 유지하면서 현재 소스만 빠르게 교체해야 하면 아래를
사용합니다. 이 경우 생성되는 `lambda-deploy-current.zip`은 기준 ZIP의 의존성을 그대로
사용하므로, 기준 ZIP이 현재 Runtime과 호환되는지 먼저 확인해야 합니다.

```powershell
python scripts\refresh_lambda_package.py `
  --base-zip dist\lambda-deploy.zip `
  --output dist\lambda-deploy-current.zip
```

배포 전에는 실제 Lambda 환경 변수를 설정한 셸에서 아래 검사를 실행합니다. 시크릿 값은
출력하지 않고 URL, 필수 키, 버킷, 수치 형식과 ZIP 구성만 검사합니다.

```powershell
python scripts\check_lambda_deployment.py `
  --production `
  --package dist\lambda-deploy.zip
```

`package_lambda.ps1`는 ZIP 생성 뒤 필수 파일과 Windows 바이너리 유입 여부를 자동으로
검사합니다. 배포 전 검사는 `OCR_INPUT_BUCKET`도 필수로 확인하므로 운영 버킷 설정 누락을
먼저 발견할 수 있습니다.

Lambda 설정:

| 항목 | 값 |
| --- | --- |
| Runtime | Python 3.11 또는 Python 3.12 |
| Handler | `ocr_service.lambda_handler.handler` |
| Timeout | 60초 이상 권장 |
| Memory | 512MB 이상 권장. 문서를 메모리에서 처리하므로 `NCLOUD_OCR_MAX_FILE_BYTES`의 3배 이상 확보 |
| Ephemeral storage | 기본값(512MB) 그대로. `/tmp`를 사용하지 않음 |

필수 환경 변수:

```env
NCLOUD_OCR_BIZ_LICENSE_API_URL=https://YOUR_INVOKE_URL.apigw.ntruss.com/custom/v1/YOUR_DOMAIN_ID/YOUR_DEPLOY_ID/document/biz-license
NCLOUD_OCR_SECRET_KEY=YOUR_SECRET_KEY
```

선택 환경 변수:

```env
OCR_INPUT_BUCKET=loovi-ocr-input
NCLOUD_OCR_API_URL=https://YOUR_INVOKE_URL.apigw.ntruss.com/custom/v1/YOUR_DOMAIN_ID/YOUR_DEPLOY_ID/general
NCLOUD_OCR_LANG=ko
NCLOUD_OCR_VERSION=V2
NCLOUD_OCR_TIMEOUT=60
NCLOUD_OCR_TEMPLATE_IDS=
NCLOUD_OCR_MAX_FILE_BYTES=52428800
```

`OCR_INPUT_BUCKET`은 운영 환경에서 반드시 설정하세요. 설정하지 않으면 호출자가 지정한 어떤 버킷이든 읽으므로, Lambda role이 접근 가능한 모든 객체를 OCR에 태울 수 있습니다.

`NCLOUD_OCR_BIZ_LICENSE_API_URL`은 공식 Document OCR 사업자등록증 URL입니다. `NCLOUD_OCR_API_URL`은 Document OCR 결과의 필드가 부족할 때 General/Template OCR fallback에 사용합니다.

IAM 권한:

```text
s3:GetObject
logs:CreateLogGroup
logs:CreateLogStream
logs:PutLogEvents
```

VPC 안에서 실행하는 경우 Ncloud OCR로 나가는 NAT/outbound 설정이 필요합니다.

## 7. CLI

로컬에서는 `.env`에 Ncloud 값을 넣은 뒤 실행합니다.

```powershell
python main.py .\data\sample.png --business-registration
```

자주 쓰는 옵션:

```powershell
python main.py .\data\sample.png
python main.py .\data\sample.png --business-registration
python main.py .\data\sample.png --text-only
python main.py .\data\sample.png --template-fields
python main.py .\data\sample.png --business-registration --output outputs\raw.json
python main.py .\data\sample.png --business-registration --template-id 12345
python main.py --help
```

저장해 둔 raw output으로 OCR 응답만 다시 확인하려면:

```powershell
python scripts\check_ocr_response_from_outputs.py
```

## 8. 내부 검증

### 8.1 외부 호출 없는 단위·회귀 테스트

```powershell
python -m compileall main.py ocr_service scripts tests
python -m unittest discover
```

`unittest`에는 Lambda 응답 6개 필드, 시크릿 마스킹 로그, 배포 사전검사와
`outputs/document_raw`의 저장된 사업자등록증 6건 회귀 검사가 포함됩니다. Ncloud, AWS,
data.go.kr을 호출하지 않습니다.

### 8.2 저장된 OCR 결과 확인

```powershell
$env:PYTHONIOENCODING = "utf-8"
python scripts\check_ocr_response_from_outputs.py
```

저장된 Document OCR 원본을 다시 파싱해 각 파일의 백엔드 응답 6개 필드를 출력합니다.
외부 OCR 호출 없이 파서 결과를 눈으로 확인할 때 사용합니다.

### 8.3 ZIP 검사

```powershell
python scripts\check_lambda_deployment.py `
  --skip-env `
  --package dist\lambda-deploy-current.zip
```

ZIP 안의 handler, `requests`, `boto3`와 Windows 전용 바이너리 유입 여부만 확인합니다.
운영 환경 변수까지 같이 확인하려면 `--skip-env` 대신 `--production`을 사용합니다.

### 8.4 Lambda 콘솔 통합 테스트

Lambda에 실제 환경 변수와 S3 권한이 설정된 뒤에만 실행합니다. 콘솔 테스트 이벤트는
아래와 같습니다.

```json
{
  "action": "ocr",
  "bucket": "실제-입력-버킷",
  "key": "team-registrations/실제-사업자등록증.png"
}
```

성공하면 proxy 봉투 없이 `companyName`, `representativeName`, `businessNumber`,
`businessOpeningDate`, `businessType`, `businessItem` 6개 필드가 최상위에 반환됩니다.
CloudWatch에서는 같은 `request_id`의 시작·성공 또는 실패 로그를 확인합니다.
