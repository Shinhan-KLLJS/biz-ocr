# 사업자등록증 검증 명세 (서버 구현용)

Lambda는 OCR과 필드 파싱만 담당한다. 사업자등록증 진위 확인, 광고업 판단, 최종 승인 판정은 백엔드 서버가 수행한다.

이 문서는 Lambda에서 제거한 검증 로직의 동작 명세다. 서버가 이 규칙을 그대로 재구현하면 기존 판정 결과와 동일하게 동작한다.

최종 승인 조건은 아래 세 가지를 모두 만족하는 경우다.

- 사업자등록증 진위 확인 통과
- 현재 운영 중인 사업자
- 광고 관련 사업자

---

## 1. 입력 값 정규화

data.go.kr로 보내기 전에 아래 형식을 강제한다. 형식이 맞지 않으면 API를 호출하지 않고 `review_required`로 처리한다.

| 필드 | 형식 | 정규화 |
| --- | --- | --- |
| `businessRegistrationNumber` | 숫자 10자리 | 숫자가 아닌 문자 제거 후 길이 10 확인 |
| `openingDate` | `YYYYMMDD` 8자리 | 숫자가 아닌 문자 제거 후 길이 8 확인 |
| `representativeName` | 문자열 | 모든 공백 제거 후 말미의 `외N명` 제거 |

대표자명 정규화 예시:

```text
"홍길동외 1명"   -> "홍길동"
"홍길동 외 1명"  -> "홍길동"
"홍길동"         -> "홍길동"
```

사업자등록증에는 공동대표를 `외 N명`으로 표기하지만 국세청 진위확인은 대표자 한 명만 받는다. 실제 사업자등록증에서 확인된 표기이며, 이 정규화가 없으면 공동대표 사업자는 진위확인에 실패한다.

---

## 2. data.go.kr 국세청 API

Base URL은 `https://api.odcloud.kr/api/nts-businessman/v1`이다.

`serviceKey`는 쿼리 파라미터로 보낸다. 공공데이터포털이 이미 URL 인코딩된 키를 발급하는 경우가 있으므로, **키에 `%`가 포함되어 있으면 그대로 사용하고 없을 때만 URL 인코딩한다.** 이중 인코딩하면 인증에 실패한다.

두 API 모두 `POST`이며 `Content-Type: application/json`, `Accept: application/json`을 보낸다.

응답 본문의 `status_code`가 `"OK"`가 아니면 실패로 처리한다. 결과는 `data` 배열의 첫 번째 항목을 사용한다.

### 2.1 진위확인 — `POST /validate`

운영에서 사용하는 모드다. 세 필드가 모두 필수다.

```json
{
  "businesses": [
    {
      "b_no": "4959240582",
      "start_dt": "20240624",
      "p_nm": "이정현"
    }
  ]
}
```

사업자명(`b_nm`), 업태, 종목, 주소는 **보내지 않는다.** OCR 값의 흔들림이 커서 일치 검증에 쓰면 정상 사업자가 반려된다.

응답 해석:

| 응답 필드 | 의미 |
| --- | --- |
| `valid == "01"` | 진위 확인 통과 (`isCertificateValid = true`) |
| `valid_msg` | 실패 사유 메시지 |
| `status` | 사업자 상태 객체. 있으면 그대로 사용 |

`status` 객체가 응답에 없으면 아래 `/status`를 한 번 더 호출해 영업 상태를 채운다.

**`valid == "01"`은 영업 중이라는 뜻이 아니다.** 실제 사업자등록증으로 확인한 결과, 진위 확인을 통과하면서 `b_stt`가 `폐업자`인 경우가 있다. 사업자등록증 자체는 진짜지만 이미 폐업한 사업자다. 진위와 영업 상태는 반드시 따로 판단해야 한다.

### 2.2 상태조회 — `POST /status`

사업자등록번호만으로 등록 여부와 영업 상태를 조회한다. 진위 확인이 아니므로 이것만으로 승인하면 안 된다. 남의 실존 사업자번호를 넣어도 통과한다.

```json
{ "b_no": ["4959240582"] }
```

응답 해석:

| 판단 | 규칙 |
| --- | --- |
| `isRegistered` | `b_stt_cd`가 비어 있지 않음 |
| `isActive` | `b_stt_cd == "01"` (계속사업자) |
| `businessStatus` | `b_stt` |
| `taxType` | `tax_type` |

**미등록 사업자는 `b_stt_cd`로 판단한다.** 실제 응답을 확인한 결과, 등록되지 않은 번호는 아래처럼 `b_stt_cd`가 빈 문자열이고 `b_stt`도 없다.

```json
{
  "b_no": "4959240582",
  "b_stt_cd": "",
  "tax_type": "국세청에 등록되지 않은 사업자등록번호입니다."
}
```

`tax_type` 문자열로 미등록을 판단하지 말 것. 실제 문구는 `"등록되지 않은"`이며, 국세청이 문구를 바꾸면 조용히 깨진다. `b_stt_cd`가 비어 있는지만 보면 충분하다.

`b_stt_cd`의 값:

| 값 | 의미 | 확인 |
| --- | --- | --- |
| `01` | 계속사업자 | 실제 응답으로 확인 |
| `02` | 휴업자 | 공공데이터포털 명세 기준. 샘플 미확보 |
| `03` | 폐업자 | 실제 응답으로 확인. `end_dt`에 폐업일(`YYYYMMDD`)이 들어온다 |
| (빈 값) | 국세청에 등록되지 않은 번호 | 실제 응답으로 확인 |

`isActive`는 `b_stt_cd == "01"`로만 판단하므로 휴업자와 폐업자가 모두 걸러진다. 폐업자를 반려할 때 `end_dt`를 `rejection_reason`에 함께 넣으면 사용자가 상황을 이해하기 쉽다.

### 2.3 비밀값 마스킹

`requests` 계열 라이브러리의 예외 메시지에는 요청 URL이 그대로 들어가고, 거기에 `serviceKey`가 실려 있다. 예외를 로그나 응답으로 내보내기 전에 반드시 마스킹한다. 원본 예외를 그대로 전파(chaining)하지 말 것.

---

## 3. 광고업 분류

입력은 사용자가 확정한 `businessType`(업태)와 `businessItem`(종목) 두 개뿐이다.

### 3.1 매칭 절차

1. 두 필드 중 값이 있는 것만 모아 공백 하나로 이어 붙인다.
2. 모든 공백을 제거하고 소문자로 바꾼다.
3. 키워드도 같은 방식으로 정규화한 뒤 부분 문자열 포함 여부로 검사한다.

### 3.2 키워드 목록

높은 신뢰도 (13개):

```text
광고대행, 광고기획, 광고제작, 광고물, 옥외광고, 전시광고,
온라인광고, 검색광고, 바이럴, 매체대행, 판촉, 판촉물, 광고
```

중간 신뢰도 (8개):

```text
마케팅대행, 홍보대행, 프로모션, 브랜딩,
콘텐츠마케팅, sns마케팅, 마케팅, 홍보
```

`광고`와 `마케팅`처럼 짧고 넓은 키워드가 목록 뒤쪽에 있다. 매칭된 키워드는 **모두** 모으되 목록 순서대로 검사하므로, 구체적인 키워드가 배열 앞에 온다.

실제 사업자등록증(`광고물제작 ... 광고대행 디자인`)으로 확인한 결과:

```text
matchedKeywords = ["광고대행", "광고물", "광고"]
confidence      = "high"
```

`광고`가 `광고대행`의 부분 문자열이라 함께 잡히지만, 판정에는 영향이 없다. 높은 신뢰도 키워드가 하나라도 있으면 `high`다.

### 3.3 판정

| 조건 | `classificationStatus` | `confidence` | `reviewRequired` | `isAdvertisingRelated` |
| --- | --- | --- | --- | --- |
| 높은 신뢰도 키워드 매칭 | `matched` | `high` | `false` | `true` |
| 중간 신뢰도만 매칭 | `matched` | `medium` | **`true`** | `true` |
| 매칭 없음 + 업태/종목 누락 | `unknown` | `unknown` | `true` | `false` |
| 매칭 없음 + 업태/종목 있음 | `not_matched` | `none` | `false` | `false` |

중간 신뢰도만 매칭되면 광고 관련으로 보되 **수동 검토 대상**이다. "마케팅"이나 "홍보"만으로는 옥외광고 매체를 집행할 사업자인지 확정할 수 없기 때문이다.

---

## 4. 최종 판정

진위/상태 결과와 광고업 분류 결과를 합쳐 하나의 상태를 만든다. **아래 순서대로 검사하고 처음 일치하는 규칙에서 멈춘다.** 순서를 바꾸면 결과가 달라진다.

| # | 조건 | status | reasonCode |
| --- | --- | --- | --- |
| 1 | 검증 입력이 누락되거나 형식 오류 | `review_required` | `VALIDATION_INPUT_INCOMPLETE` |
| 2 | `isRegistered == false` | `rejected` | `UNREGISTERED_BUSINESS` |
| 3 | `isCertificateValid == false` | `rejected` | `INVALID_CERTIFICATE` |
| 4 | `isActive == false` | `rejected` | `INACTIVE_BUSINESS` |
| 5 | 업태/종목 누락 | `review_required` | `ADVERTISING_CLASSIFICATION_INPUT_INCOMPLETE` |
| 6 | `isAdvertisingRelated == false` | `rejected` | `NON_ADVERTISING_BUSINESS` |
| 7 | 광고업 분류가 `reviewRequired` | `review_required` | `ADVERTISING_CLASSIFICATION_REVIEW_REQUIRED` |
| 8 | `isCertificateValid == true` | `accepted` | `ACCEPTED` |
| 9 | 그 외 | `review_required` | `VALIDATION_UNDETERMINED` |

9번은 `status` 모드로만 검증했을 때 도달한다. 영업 중인 사업자로 확인됐어도 진위 확인을 거치지 않았으므로 승인하지 않는다.

### 실제 사업자등록증으로 확인한 판정 경로

이 명세대로 재구현해 실제 data.go.kr에 질의한 결과다. 서버 구현이 아래 네 경로를 모두 재현하면 신뢰할 수 있다.

| 문서 특징 | 진위 | 영업 상태 | 광고업 | 판정 |
| --- | --- | --- | --- | --- |
| 광고물제작·광고대행 업종 | 통과 | 계속사업자 | `high` | `accepted` / `ACCEPTED` |
| 정보통신업 | 통과 | 계속사업자 | 매칭 없음 | `rejected` / `NON_ADVERTISING_BUSINESS` |
| 공동대표(`외 1명`), 제조·소매업 | 통과 | 계속사업자 | 매칭 없음 | `rejected` / `NON_ADVERTISING_BUSINESS` |
| 음식점업 | **통과** | **폐업자** | 매칭 없음 | `rejected` / `INACTIVE_BUSINESS` |

마지막 행이 판정 순서가 왜 중요한지 보여준다. 진위 확인을 통과했으므로 8번 규칙만 있었다면 `accepted`가 나왔을 것이다. 4번(`isActive == false`)이 먼저 걸러야 한다.

세 번째 행은 §1의 대표자명 정규화가 없으면 진위 확인 자체가 실패하는 경우다. OCR은 `홍길동외 1명` 형태의 원문을 그대로 넘기므로, `외N명`을 떼지 않으면 국세청이 대표자를 찾지 못한다.

---

## 5. DB 적재

판정이 끝나면 `team_business_registrations`에 한 번 UPSERT한다. `team_id`가 UNIQUE이므로 재제출은 UPDATE로 동작한다.

### 5.1 컬럼별 출처

Lambda가 준 값은 사용자가 수정하기 전의 추정값이다. **저장하는 값은 사용자가 확정해 제출한 값**이며, Lambda 응답을 그대로 쓰지 않는다.

| 컬럼 | 출처 |
| --- | --- |
| `team_id`, `uploaded_by_user_id` | 서버의 인증 세션 |
| `document_storage_key` | 서버가 업로드 시 정한 S3 키 |
| `business_number` | 사용자 확정값. 숫자 10자리 |
| `company_name` | 사용자 확정값 |
| `representative_name` | 사용자 확정값 |
| `opening_date` | 사용자 확정값. `YYYYMMDD` 문자열을 `DATE`로 변환 |
| `verification_status` | 아래 판정 매핑 |
| `rejection_reason` | 판정 메시지 |
| `verified_at` | `APPROVED`일 때만 `now()` |

`opening_date`는 저장해두어야 나중에 서버가 스스로 재검증할 수 있다. 진위확인에 개업일자가 필수인데 저장하지 않으면, 승인된 사업자의 폐업 여부를 다시 확인할 때 사용자에게 값을 또 물어봐야 한다.

### 5.2 판정 매핑

| status | verification_status | 비고 |
| --- | --- | --- |
| `accepted` | `APPROVED` | `verified_at = now()` |
| `rejected` | `REJECTED` | `rejection_reason`에 판정 메시지 |
| `review_required` | `PENDING` | `rejection_reason`에 판정 메시지 |

### 5.3 재제출 시 상태 퇴행

`team_id`가 UNIQUE라 UPSERT가 UPDATE로 동작하므로, **이미 `APPROVED`인 팀이 잘못된 문서로 재제출하면 승인 상태가 `REJECTED`로 덮인다.** ERD가 이력 미보관을 의도했더라도, 현재 상태가 퇴행하는 것은 별개의 문제다.

`APPROVED` 상태의 재제출을 막거나, 재제출은 항상 `PENDING`으로만 전이시키는 규칙이 필요하다.

---

## 6. OCR 단계에서는 저장하지 않는다

OCR 응답을 받은 시점에는 DB에 쓰지 않는다. 사용자가 아직 확인도 하지 않은 값으로 기존 `APPROVED` 행을 덮어쓰게 되기 때문이다.

사용자가 OCR만 하고 이탈했다 돌아오면 OCR을 다시 호출한다. 문서는 S3에 남아 있으므로 재업로드는 필요 없다.

---

## 7. 검증하지 않는 값

`companyName`, `businessType`, `businessItem`은 data.go.kr가 확인해주지 않는다. 사용자가 화면에서 수정한 값이 그대로 판정에 쓰인다.

즉 **실제 사업자등록증에 "음식점업 / 한식"이라 적혀 있어도 폼에서 "서비스업 / 광고대행"으로 고쳐 제출하면 `accepted`가 나온다.** 사업자등록번호·대표자명·개업일자 세 개만 진짜라면 진위 확인은 통과하기 때문이다.

서버는 `document_storage_key`로 원본 문서를 보관하므로 사후 감사는 가능하다. 자동으로 막으려면 OCR이 읽은 업태/종목과 사용자가 제출한 값을 비교해, 다르면 `review_required`로 강등하는 정책이 필요하다.
