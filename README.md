# 사업자등록증 OCR/검증 Lambda API 명세

사업자등록증 이미지/PDF를 OCR 처리한 뒤, 프론트에서 사용자가 값을 확인/수정하고, 수정된 값을 기준으로 사업자등록증 진위와 상태를 검증하는 Lambda API입니다.

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

권장 처리 순서:

```text
OCR request
  -> S3 파일 읽기 (메모리, /tmp 미사용)
  -> Ncloud 사업자등록증 Document OCR 호출
  -> 필드 부족 시 General/Template OCR fallback
  -> 사업자등록증 필드 파싱
  -> 프론트 수정 화면에 추정값 반환

Frontend
  -> 사용자가 OCR 추정값 확인/수정

Verification request
  -> 사업자등록번호/대표자명/개업일자로 data.go.kr 진위/상태 확인
  -> 수정된 업태/종목 기준 광고업 판단
  -> 최종 판정 반환
```

Lambda는 아래 방식으로 API 동작을 구분합니다.

| 구분 | 권장 경로 | 대체 입력 | 동작 |
| --- | --- | --- | --- |
| OCR | `/business-registrations/ocr` | `"action": "ocr"` | OCR과 파싱만 수행 |
| 검증 | `/business-registrations/verification` | `"action": "verification"` | 사용자가 수정한 값으로 검증/판정 |

OCR 후 즉시 검증까지 수행하는 기존 단일 호출 방식은 지원하지 않습니다. API Gateway 경로나 `action` 값으로 OCR/검증 동작을 명확히 지정해야 합니다.

## 2. Request

### OCR Request Body

```json
{
  "bucket": "loovi-ocr-input",
  "key": "incoming/business-registration.png"
}
```

OCR API는 CLOVA OCR과 파싱만 수행합니다. 이 단계에서는 국세청 검증을 호출하지 않으며, 프론트가 수정할 수 있는 추정값과 누락 필드, 경고를 반환합니다.

### Verification Request Body

```json
{
  "business": {
    "businessRegistrationNumber": "3688803013",
    "representativeName": "이상옥",
    "openingDate": "20240624",
    "businessType": "서비스업",
    "businessItem": "광고대행"
  },
  "businessRegistrationValidation": "authenticity"
}
```

검증 API는 OCR 원본값이 아니라 프론트에서 사용자가 확정한 값을 기준으로 진위/상태와 광고업 여부를 최종 판정합니다.

검증 요청의 `business`에는 data.go.kr 진위확인 필수값과 광고업 판단 필수값을 넣습니다. 단, data.go.kr로 전송하는 값은 사업자등록번호, 대표자명, 개업일자 3개뿐입니다.

| 필드 | 필수 | 설명 |
| --- | --- | --- |
| `businessRegistrationNumber` | 예 | 숫자 10자리. `-` 같은 기호 제거 후 전송 |
| `representativeName` | 예 | 대표자 성명. 외국인 사업자는 영문명 입력 |
| `openingDate` | 예 | 사업자등록증의 개업연월일. `YYYYMMDD` 형식으로 `-` 같은 기호 제거 후 전송 |
| `businessType` | 예 | 프론트에서 확정한 업태. 광고업 판단에 사용 |
| `businessItem` | 예 | 프론트에서 확정한 종목. 광고업 판단에 사용 |

### 필수 입력값

OCR 요청에는 처리할 S3 파일 위치가 필요합니다. 운영 연동에서는 아래처럼 `bucket`과 `key`를 보내는 방식을 권장합니다.

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

S3 업로드 이벤트로 Lambda를 직접 트리거하는 방식은 지원하지 않습니다. OCR 결과를 돌려받을 호출자가 없어 결과가 버려지기 때문입니다. 프론트가 S3 업로드를 마친 뒤 `/business-registrations/ocr`을 직접 호출해야 합니다. S3 이벤트 형태의 payload를 보내더라도 `action` 또는 경로로 동작을 지정해야 처리됩니다.

S3 객체는 `/tmp`에 내려받지 않고 메모리로 읽습니다. Lambda의 `/tmp`는 warm 컨테이너에서 재사용되어 파일이 쌓이기 때문입니다. 객체 크기는 본문을 읽기 전에 `head_object`로 확인하며, 지원하지 않는 확장자는 S3를 읽기 전에 거절합니다.

### 사업자 검증 옵션

검증 요청에서 사업자등록증 진위와 사업자 현황을 확인하려면 아래 값을 같이 보내세요.

```json
{
  "businessRegistrationValidation": "authenticity"
}
```

`authenticity`는 사업자등록증 진위 확인을 수행하고, 응답에 현재 영업 상태와 과세 유형도 함께 포함합니다. 검증 성공 시 `status = "verified"`를 반환합니다.

다른 값도 지원하지만 사업자등록증 진위 확인용으로는 권장하지 않습니다.

| 값 | 동작 |
| --- | --- |
| `authenticity` | 진위 확인 + 사업자 상태 확인. 운영 권장값 |
| 비움 | 기본값 `authenticity`로 처리 |

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

### OCR Success Body

프론트 수정 화면에는 OCR 추정값과 검토 정보를 반환합니다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `status` | string | OCR 처리 상태. `ocr_completed` |
| `documentType` | string | 문서 유형. `businessRegistrationCertificate` |
| `business` | object | 프론트에서 수정할 사업자 정보 |
| `missingFields` | array | OCR에서 채우지 못한 필드 |
| `warnings` | array | 파서가 남긴 검토 경고 |
| `source` | object | 입력 S3 위치 |

OCR 응답의 `business`에는 `companyName`, `representativeName`, `businessRegistrationNumber`, `openingDate`, `businessAddress`, `businessType`, `businessItem`을 포함합니다. OCR 원문이 애매한 경우 `businessTypeCandidates`, `businessItemsRaw`도 함께 내려보내 프론트가 선택/수정할 수 있게 합니다.

OCR 응답의 `businessRegistrationNumber`는 숫자 10자리, `openingDate`는 `YYYYMMDD` 형식으로 내려갑니다. OCR 값이 이 규격으로 정규화되지 않으면 해당 값은 `null`이고 `missingFields`에 포함됩니다.

### Verification Success Body

검증 API는 사업자등록증 진위/현황과 광고업 판단을 합친 최종 결정을 반환합니다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `status` | string | 최종 판정. `accepted`, `rejected`, `review_required` |
| `business` | object | 검증과 광고업 판단에 사용한 정보 |
| `verification` | object | 진위/현황 확인 결과와 사유 |
| `advertisingClassification` | object | 업태/종목 기반 광고업 판단 결과 |
| `eligibility` | object | 최종 승인 가능 여부와 사유 |

### business

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `businessRegistrationNumber` | string/null | 사업자등록번호 |
| `representativeName` | string/null | 대표자명 |
| `openingDate` | string/null | 개업연월일 |
| `businessType` | string/null | 업태 |
| `businessItem` | string/null | 종목 |

### verification

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `isCertificateValid` | boolean/null | 사업자등록증 진위 확인 통과 여부 |
| `isRegistered` | boolean/null | 사업자등록번호 등록 여부 |
| `isActive` | boolean/null | 현재 운영 중인 사업자인지 여부 |
| `validationMode` | string/null | 사용한 검증 모드. `status` 또는 `authenticity` |
| `validationCode` | string/null | data.go.kr 진위확인 코드 |
| `validationMessage` | string/null | data.go.kr 진위확인 메시지 |
| `businessStatus` | string/null | 사업자 상태 |
| `taxType` | string/null | 과세 유형 |
| `reasonCode` | string/null | 판정 사유 코드 |
| `message` | string/null | 사용자 또는 운영자에게 보여줄 수 있는 판정 메시지 |

`status = "accepted"`가 되려면 `isCertificateValid`, `isActive`, `advertisingClassification.isAdvertisingRelated`가 모두 `true`이고 광고업 판단이 수동 검토 대상이 아니어야 합니다.

`authenticity` 검증은 data.go.kr Swagger 예시의 필수값인 사업자등록번호, 개업일자, 대표자명만 전송합니다. OCR로 추출한 사업자명, 업태, 종목, 주소는 진위확인 요청에 넣지 않습니다.

주요 `status`:

| status | 의미 |
| --- | --- |
| `accepted` | 진위/현황 확인과 광고업 판단을 모두 통과 |
| `rejected` | 진위 실패, 미등록, 비활성, 비광고 사업자 등 정책상 거절 |
| `review_required` | 필수값 누락, 형식 오류, 넓은 광고 키워드, 검증 결과 불확정 등 수동 검토 필요 |

주요 `reasonCode`:

| reasonCode | 의미 |
| --- | --- |
| `ACCEPTED` | 승인 |
| `INVALID_CERTIFICATE` | 사업자등록증 진위 확인 실패 |
| `UNREGISTERED_BUSINESS` | 등록된 사업자로 확인되지 않음 |
| `INACTIVE_BUSINESS` | 현재 운영 중인 사업자가 아님 |
| `VALIDATION_INPUT_INCOMPLETE` | 검증 필수값 누락 또는 형식 오류 |
| `VALIDATION_UNDETERMINED` | 검증 결과 불확정 |
| `NON_ADVERTISING_BUSINESS` | 광고 관련 사업자로 분류되지 않음 |
| `ADVERTISING_CLASSIFICATION_INPUT_INCOMPLETE` | 광고업 판단 필수값 누락 |
| `ADVERTISING_CLASSIFICATION_REVIEW_REQUIRED` | 광고 관련성이 애매해 수동 검토 필요 |

내부적으로는 data.go.kr 원본 응답과 누락 필드 등을 사용해 위 값을 계산합니다. 이 내부 근거 데이터는 기본 클라이언트 응답에 포함하지 않습니다.

## 4. Example

### OCR Request

```json
{
  "bucket": "loovi-ocr-input",
  "key": "incoming/business-registration.png"
}
```

### OCR Response Body

```json
{
  "status": "ocr_completed",
  "documentType": "businessRegistrationCertificate",
  "business": {
    "companyName": "신한 KLLJS",
    "representativeName": "이정현",
    "businessRegistrationNumber": "4959240582",
    "openingDate": "20240624",
    "businessAddress": "서울특별시 송파구",
    "businessType": "서비스업",
    "businessItem": "광고대행"
  },
  "missingFields": [],
  "warnings": []
}
```

### Verification Request

```json
{
  "business": {
    "businessRegistrationNumber": "4959240582",
    "representativeName": "이정현",
    "openingDate": "20240624",
    "businessType": "서비스업",
    "businessItem": "광고대행"
  },
  "businessRegistrationValidation": "authenticity"
}
```

### Verification Response Body

```json
{
  "status": "accepted",
  "business": {
    "businessRegistrationNumber": "4959240582",
    "representativeName": "이정현",
    "openingDate": "20240624",
    "businessType": "서비스업",
    "businessItem": "광고대행"
  },
  "verification": {
    "isCertificateValid": true,
    "isRegistered": true,
    "isActive": true,
    "validationMode": "authenticity",
    "validationCode": "01",
    "validationMessage": null,
    "businessStatus": "계속사업자",
    "taxType": "부가가치세 일반과세자",
    "reasonCode": "ACCEPTED",
    "message": "현재 운영 중인 광고 관련 사업자로 확인되었습니다."
  },
  "advertisingClassification": {
    "isAdvertisingRelated": true,
    "classificationStatus": "matched",
    "confidence": "high",
    "matchedKeywords": ["광고대행"],
    "reviewRequired": false
  },
  "eligibility": {
    "isEligible": true,
    "isCertificateValid": true,
    "isRegistered": true,
    "isActive": true,
    "isAdvertisingRelated": true,
    "reasonCode": "ACCEPTED",
    "message": "현재 운영 중인 광고 관련 사업자로 확인되었습니다."
  }
}
```

## 5. Error Response

시스템 처리 실패 시 `statusCode: 500`을 반환합니다. 사업자등록증이 가짜이거나 현재 운영 중이 아닌 경우는 시스템 오류가 아니므로 `statusCode: 200` 안의 `status = "rejected"`로 반환합니다.

외부 API 호출이 실패하면 `ExternalServiceError`로 감싸 반환합니다. 원본 예외 메시지에는 `serviceKey`가 담긴 요청 URL이 들어가므로, 응답과 CloudWatch 로그에 나가기 전에 비밀값을 `***REDACTED***`로 가립니다.

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
| Memory | 512MB 이상 권장. 문서를 메모리에서 처리하므로 `NCLOUD_OCR_MAX_FILE_BYTES`의 3배 이상 확보 |
| Ephemeral storage | 기본값(512MB) 그대로. `/tmp`를 사용하지 않음 |

필수 환경 변수:

```env
NCLOUD_OCR_BIZ_LICENSE_API_URL=https://YOUR_INVOKE_URL.apigw.ntruss.com/custom/v1/YOUR_DOMAIN_ID/YOUR_DEPLOY_ID/document/biz-license
NCLOUD_OCR_SECRET_KEY=YOUR_SECRET_KEY
```

선택 환경 변수:

```env
NCLOUD_OCR_API_URL=https://YOUR_INVOKE_URL.apigw.ntruss.com/custom/v1/YOUR_DOMAIN_ID/YOUR_DEPLOY_ID/general
NCLOUD_OCR_LANG=ko
NCLOUD_OCR_VERSION=V2
NCLOUD_OCR_TIMEOUT=60
NCLOUD_OCR_TEMPLATE_IDS=
NCLOUD_OCR_MAX_FILE_BYTES=52428800
DATA_GO_KR_SERVICE_KEY=YOUR_DATA_GO_KR_SERVICE_KEY
DATA_GO_KR_TIMEOUT=30
DATA_GO_KR_BUSINESS_VALIDATION=
DATA_GO_KR_NTS_BUSINESSMAN_BASE_URL=https://api.odcloud.kr/api/nts-businessman/v1
```

`NCLOUD_OCR_BIZ_LICENSE_API_URL`은 공식 Document OCR 사업자등록증 URL입니다. `NCLOUD_OCR_API_URL`은 Document OCR 결과의 필드가 부족할 때 기존 General/Template OCR fallback에 사용합니다.

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
