# OCR Lambda API 명세

사업자등록증 이미지/PDF를 OCR 처리하고, 사업자등록증 진위 확인과 최종 승인 판정을 반환하는 Lambda API입니다.

최종 승인 조건은 아래 3가지를 모두 만족하는 경우입니다.

- 사업자등록증 진위 확인 통과
- 현재 운영 중인 사업자
- 광고 관련 사업자

## 1. API 개요

| 항목 | 값 |
| --- | --- |
| Lambda Handler | `ocr_service.lambda_handler.handler` |
| Runtime | Python 3.11 또는 Python 3.12 |
| 입력 파일 위치 | S3 object |
| 지원 파일 | `.jpg`, `.jpeg`, `.png`, `.pdf`, `.tif`, `.tiff` |
| 응답 형식 | API Gateway Lambda proxy response |
| 권장 검증 모드 | `authenticity` |

처리 순서:

```text
Lambda request
  -> S3 파일 다운로드
  -> Ncloud CLOVA OCR 호출
  -> 사업자등록증 필드 파싱
  -> data.go.kr 사업자등록증 진위 확인
  -> 광고 사업자 분류
  -> 최종 판정 반환
```

## 2. Request

### 권장 Request Body

```json
{
  "bucket": "loovi-ocr-input",
  "key": "incoming/business-registration.png",
  "businessRegistrationValidation": "authenticity"
}
```

`businessRegistrationValidation: "authenticity"`는 사업자등록증 진위 확인을 수행합니다. 이 응답에는 영업 상태와 과세 유형 같은 사업자 상태 정보도 함께 포함됩니다.

### 필수 입력값

요청에는 처리할 S3 파일 위치가 필요합니다. 운영 연동에서는 아래처럼 `bucket`과 `key`를 보내는 방식을 권장합니다.

```json
{
  "bucket": "loovi-ocr-input",
  "key": "incoming/business-registration.png"
}
```

S3 위치는 아래 방식도 지원합니다.

```json
{
  "s3": {
    "bucket": "loovi-ocr-input",
    "key": "incoming/business-registration.png"
  }
}
```

```json
{
  "s3Uri": "s3://loovi-ocr-input/incoming/business-registration.png"
}
```

S3 업로드 이벤트로 Lambda를 연결한 경우에는 S3 이벤트의 첫 번째 record에서 bucket/key를 읽습니다.

### 사업자 검증 옵션

최종 승인 판정까지 받으려면 아래 값을 같이 보내세요.

```json
{
  "businessRegistrationValidation": "authenticity"
}
```

`authenticity`는 사업자등록증 진위 확인을 수행하고, 응답에 현재 영업 상태와 과세 유형도 함께 포함합니다. 이 서비스에서 `status = "accepted"`를 받으려면 `authenticity` 사용이 필요합니다.

다른 값도 지원하지만 운영 승인 판정용으로는 권장하지 않습니다.

| 값 | 동작 |
| --- | --- |
| `authenticity` | 진위 확인 + 사업자 상태 확인. 운영 권장값 |
| `status` | 사업자번호 상태만 조회. 진위 확인은 하지 않음 |
| 비움 | 검증하지 않음. 최종 판정은 `review_required` |
| `false`, `0`, `none`, `off` | 검증을 끔 |

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
  "headers": {
    "Content-Type": "application/json; charset=utf-8"
  },
  "body": "{...JSON 문자열...}"
}
```

API Gateway 또는 Lambda Function URL을 통하면 `body` 내부 JSON이 HTTP 응답 본문으로 전달됩니다.

### Success Body

클라이언트에는 화면 표시와 최종 판단에 필요한 값만 반환합니다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `status` | string | 최종 판정. `accepted`, `rejected`, `review_required` |
| `business` | object | 화면에 표시할 사업자 정보 |
| `eligibility` | object | 승인 가능 여부와 사유 |

### business

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `companyName` | string/null | 사업자명 |
| `representativeName` | string/null | 대표자명 |
| `businessRegistrationNumber` | string/null | 사업자등록번호 |

### eligibility

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `isEligible` | boolean | 최종 승인 가능 여부 |
| `isCertificateValid` | boolean/null | 사업자등록증 진위 확인 통과 여부 |
| `isActive` | boolean/null | 현재 운영 중인 사업자인지 여부 |
| `isAdvertisingRelated` | boolean/null | 광고 관련 사업자인지 여부 |
| `reasonCode` | string/null | 판정 사유 코드 |
| `message` | string/null | 사용자 또는 운영자에게 보여줄 수 있는 판정 메시지 |

`status = "accepted"`가 되려면 `isCertificateValid`, `isActive`, `isAdvertisingRelated`가 모두 `true`여야 합니다.

주요 `status`:

| status | 의미 |
| --- | --- |
| `accepted` | 광고업 관련 계속 사업자로 확인됨 |
| `rejected` | 진위 실패, 미등록, 비활성, 비광고 사업자 등 정책상 거절 |
| `review_required` | OCR 필드 누락, 검증 미수행, 애매한 광고 분류 등 수동 검토 필요 |

주요 `reasonCode`:

| reasonCode | 의미 |
| --- | --- |
| `ACCEPTED` | 승인 |
| `INVALID_CERTIFICATE` | 사업자등록증 진위 확인 실패 |
| `UNREGISTERED_BUSINESS` | 등록된 사업자로 확인되지 않음 |
| `INACTIVE_BUSINESS` | 현재 운영 중인 사업자가 아님 |
| `NON_ADVERTISING_BUSINESS` | 광고 관련 사업자로 분류되지 않음 |
| `MISSING_REQUIRED_FIELDS` | 필수 OCR 필드 누락 |
| `VALIDATION_REQUIRED` | 검증 결과가 없어 최종 승인 불가 |
| `ADVERTISING_CLASSIFICATION_REVIEW_REQUIRED` | 광고 관련성이 애매해 수동 검토 필요 |

내부적으로는 OCR 원문, data.go.kr 원본 응답, 광고 키워드 매칭 결과, 누락 필드 등을 사용해 위 값을 계산합니다. 이 내부 근거 데이터는 기본 클라이언트 응답에 포함하지 않습니다.

## 4. Example

### Request

```json
{
  "bucket": "loovi-ocr-input",
  "key": "incoming/business-registration.png",
  "businessRegistrationValidation": "authenticity"
}
```

### Response Body

```json
{
  "status": "accepted",
  "business": {
    "companyName": "신한 KLLJS",
    "representativeName": "이정현",
    "businessRegistrationNumber": "49-592-40582"
  },
  "eligibility": {
    "isEligible": true,
    "isCertificateValid": true,
    "isActive": true,
    "isAdvertisingRelated": true,
    "reasonCode": "ACCEPTED",
    "message": "현재 운영 중인 광고 관련 사업자로 확인되었습니다."
  }
}
```

## 5. Error Response

시스템 처리 실패 시 `statusCode: 500`을 반환합니다. 사업자등록증이 가짜이거나 현재 운영 중이 아닌 경우는 시스템 오류가 아니므로 `statusCode: 200` 안의 `status = "rejected"`로 반환합니다.

```json
{
  "statusCode": 500,
  "headers": {
    "Content-Type": "application/json; charset=utf-8"
  },
  "body": "{\"error\":\"ValueError\",\"message\":\"Missing S3 object location. Provide bucket/key, s3.bucket/s3.key, s3Uri, or an S3 event.\"}"
}
```

| 에러/증상 | 확인할 것 |
| --- | --- |
| `Missing S3 object location` | S3 위치 입력이 있는지 확인 |
| `AccessDenied` | Lambda role의 `s3:GetObject` 권한 |
| `Unsupported file format` | 지원 확장자 여부 |
| `File is too large for OCR request` | 파일 크기와 `NCLOUD_OCR_MAX_FILE_BYTES` |
| `Missing required environment variable` | 필수 환경 변수 설정 |
| OCR/API timeout | Lambda timeout, VPC NAT, outbound 보안 그룹 |
| 검증 실패 | `DATA_GO_KR_SERVICE_KEY`, OCR 필수 필드 추출 여부 |

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
| Memory | 512MB 이상 권장 |

필수 환경 변수:

```env
NCLOUD_OCR_API_URL=https://YOUR_INVOKE_URL.apigw.ntruss.com/custom/v1/YOUR_DOMAIN_ID/YOUR_DEPLOY_ID/general
NCLOUD_OCR_SECRET_KEY=YOUR_SECRET_KEY
```

선택 환경 변수:

```env
NCLOUD_OCR_LANG=ko
NCLOUD_OCR_VERSION=V2
NCLOUD_OCR_TIMEOUT=60
NCLOUD_OCR_TEMPLATE_IDS=
NCLOUD_OCR_MAX_FILE_BYTES=52428800
OCR_DOWNLOAD_DIR=/tmp
DATA_GO_KR_SERVICE_KEY=YOUR_DATA_GO_KR_SERVICE_KEY
DATA_GO_KR_TIMEOUT=30
DATA_GO_KR_BUSINESS_VALIDATION=
DATA_GO_KR_NTS_BUSINESSMAN_BASE_URL=https://api.odcloud.kr/api/nts-businessman/v1
```

IAM 권한:

```text
s3:GetObject
logs:CreateLogGroup
logs:CreateLogStream
logs:PutLogEvents
```

VPC 안에서 실행하는 경우 Ncloud OCR과 data.go.kr로 나가는 NAT/outbound 설정이 필요합니다.

## 7. CLI

로컬에서는 `.env`에 Ncloud 값을 넣은 뒤 실행합니다.

```powershell
python main.py .\data\sample.png --business-registration-validation authenticity
```

자주 쓰는 옵션:

```powershell
python main.py .\data\sample.png
python main.py .\data\sample.png --business-registration
python main.py .\data\sample.png --text-only
python main.py .\data\sample.png --template-fields
python main.py .\data\sample.png --business-registration --output outputs\raw.json
python main.py .\data\sample.png --business-registration-validation status
python main.py .\data\sample.png --business-registration-validation authenticity
python main.py .\data\sample.png --business-registration --template-id 12345
python main.py --help
```

## 8. Verification

```powershell
python -m compileall main.py ocr_service tests
python -m unittest discover
```
