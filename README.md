# 사업자등록증 OCR Lambda API 명세

사업자등록증 이미지/PDF를 OCR 처리해, 프론트가 사용자에게 보여주고 수정하게 할 추정값을 반환하는 Lambda API입니다.

**이 Lambda는 OCR과 필드 파싱만 수행합니다.** 사업자등록증 진위 확인, 광고업 판단, 최종 승인 판정, DB 적재는 모두 백엔드 서버가 담당합니다. 서버가 구현해야 할 검증 규칙은 [docs/server-verification-spec.md](docs/server-verification-spec.md)에 있습니다.

## 1. 전체 흐름

```text
로그인
  -> 팀 생성 화면
  -> 사업자등록증 업로드 (S3)
  -> 프론트가 이 Lambda의 OCR API 호출
  -> 사용자가 OCR 추정값 확인/수정
  -> "팀 생성하기" -> 서버가 진위 확인 + 광고업 판단 후 DB 적재
```

| 항목 | 값 |
| --- | --- |
| Lambda Handler | `ocr_service.lambda_handler.handler` |
| Runtime | Python 3.11 또는 Python 3.12 |
| 입력 파일 위치 | S3 object |
| 지원 파일 | `.jpg`, `.jpeg`, `.png`, `.pdf`, `.tif`, `.tiff` |
| 응답 형식 | API Gateway Lambda proxy response |
| 동작 | OCR과 파싱만. 외부 검증 없음 |

동작 지정은 API Gateway 경로 `/business-registrations/ocr` 또는 요청 본문의 `"action": "ocr"`로 합니다. 그 외 입력은 모두 `400 UnsupportedOperation`입니다.

S3 업로드 이벤트로 Lambda를 직접 트리거하는 방식은 지원하지 않습니다. OCR 결과를 돌려받을 호출자가 없어 결과가 버려지기 때문입니다.

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

Lambda는 항상 아래 proxy response 형식으로 반환합니다.

```json
{
  "statusCode": 200,
  "headers": { "Content-Type": "application/json; charset=utf-8" },
  "body": "{...JSON 문자열...}"
}
```

### Success Body

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `status` | string | 항상 `ocr_completed` |
| `documentType` | string | `businessRegistrationCertificate` |
| `business` | object | 프론트에서 수정할 사업자 정보 |
| `missingFields` | array | OCR에서 채우지 못한 필드 |
| `warnings` | array | 파서가 남긴 검토 경고 |
| `source` | object | 입력 S3 위치 |

```json
{
  "status": "ocr_completed",
  "documentType": "businessRegistrationCertificate",
  "business": {
    "companyName": "신한 KLLJS",
    "representativeName": "이정현",
    "businessRegistrationNumber": "4959240582",
    "openingDate": "20240624",
    "businessType": "서비스업",
    "businessItem": "광고대행"
  },
  "missingFields": [],
  "warnings": []
}
```

`businessRegistrationNumber`는 숫자 10자리, `openingDate`는 `YYYYMMDD`로 정규화해 내려갑니다. 서버가 그대로 data.go.kr에 보낼 수 있는 형식입니다. 이 규격으로 정규화되지 않으면 해당 값은 `null`이고 `missingFields`에 포함됩니다.

OCR 원문이 애매한 경우 `businessTypeCandidates`, `businessItemsRaw`도 함께 내려보내 프론트가 선택/수정할 수 있게 합니다.

**사업장주소는 응답에 넣지 않습니다.** DB에 저장하지도, 검증에 쓰지도 않는 개인정보이기 때문입니다. 필수 필드에서도 빠졌으므로 주소를 읽지 못했다는 이유로 보조 OCR을 다시 호출하지 않습니다.

응답에는 `advertisingClassification`, `verification`, `eligibility` 같은 판정 결과가 없습니다. 그 계산은 서버가 합니다.

### 서버가 이어받는 값

OCR 응답의 `business`는 **사용자가 수정하기 전의 추정값**입니다. 서버는 사용자가 확정한 값을 기준으로 검증해야 합니다.

| OCR 응답 필드 | 서버 용도 |
| --- | --- |
| `businessRegistrationNumber` | data.go.kr 진위확인 · `business_number` |
| `representativeName` | data.go.kr 진위확인 · `representative_name` |
| `openingDate` | data.go.kr 진위확인 · `opening_date` |
| `companyName` | `company_name` (검증 대상 아님) |
| `businessType`, `businessItem` | 광고업 판단 (검증 대상 아님) |

## 4. Error Response

| statusCode | 언제 | 예외 |
| --- | --- | --- |
| `400` | 호출자가 고칠 수 있는 입력 오류 | `ValueError`, `UnsupportedOperation` |
| `502` | Ncloud OCR 장애 | `ExternalServiceError` |
| `500` | 그 외 예기치 못한 오류 | 나머지 |

외부 API 호출이 실패하면 `ExternalServiceError`로 감쌉니다. 원본 예외 메시지에는 요청 URL과 시크릿이 섞일 수 있으므로, 응답과 CloudWatch 로그에 나가기 전에 비밀값을 `***REDACTED***`로 가립니다.

```json
{
  "statusCode": 400,
  "headers": { "Content-Type": "application/json; charset=utf-8" },
  "body": "{\"error\":\"ValueError\",\"message\":\"Missing S3 object location. Provide bucket/key, s3.bucket/s3.key, s3Uri, or an S3 event.\"}"
}
```

| 에러/증상 | statusCode | 확인할 것 |
| --- | --- | --- |
| `Missing S3 object location` | 400 | S3 위치 입력이 있는지 확인 |
| `Bucket is not allowed for OCR input` | 400 | `OCR_INPUT_BUCKET`과 요청 버킷이 같은지 확인 |
| `Unsupported file format` | 400 | 지원 확장자 여부 |
| `File is too large for OCR request` | 400 | 파일 크기와 `NCLOUD_OCR_MAX_FILE_BYTES` |
| OCR timeout, Ncloud 장애 | 502 | Lambda timeout, VPC NAT, outbound 보안 그룹 |
| `AccessDenied` | 500 | Lambda role의 `s3:GetObject` 권한 |
| `Missing required environment variable` | 500 | 필수 환경 변수 설정 |

## 5. 호출자 보안

프론트가 이 Lambda를 직접 호출하는 구조에서는 아래 두 가지를 반드시 처리해야 합니다.

**객체 키 조작.** 브라우저는 `bucket`과 `key`를 마음대로 바꿀 수 있습니다. `OCR_INPUT_BUCKET`은 다른 버킷을 막지만 **같은 버킷 안의 다른 팀 문서는 막지 못합니다.** 서버가 `teams/{teamId}/` 형태로 키를 직접 정하고, 프론트에는 조작할 수 없는 형태로 전달해야 합니다. presigned URL로 문서를 넘기면 서명이 버킷·키·만료를 모두 덮으므로 이 문제가 사라집니다.

**인증.** API Gateway를 열어두면 누구나 CLOVA OCR을 호출할 수 있습니다. 최소한 JWT authorizer를 붙여 서버가 발급한 로그인 토큰을 검증하세요.

## 6. Deployment Spec

패키지 생성:

```powershell
.\scripts\package_lambda.ps1
```

생성 파일:

```text
dist\lambda-deploy.zip
```

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

## 8. Verification

```powershell
python -m compileall main.py ocr_service tests
python -m unittest discover
```
