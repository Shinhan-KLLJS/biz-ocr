"""사업자등록증 파싱에 쓰는 고정 라벨과 키워드를 정의한다."""

# 이 목록은 두 가지를 동시에 결정한다.
# 1. 응답에 노출할 필드 (parser.select_required_business_fields가 이 키만 남긴다)
# 2. 누락 시 fallback OCR을 다시 부를 필드 (services.has_missing_required_business_fields)
#
# 사업장주소는 DB에 저장하지도, data.go.kr 검증에 쓰지도 않으므로 빼둔다.
# 주소 하나 때문에 General OCR을 한 번 더 호출하던 비용도 함께 사라진다.
# LABEL_ALIASES와 text_fields의 주소 패턴은 원문 파싱 앵커로 남긴다.
REQUIRED_BUSINESS_FIELDS = {
    "businessRegistrationNumber": "사업자등록번호",
    "companyName": "상호(단체명 등)",
    "representativeName": "대표자명",
    "openingDate": "개업연월일",
    "businessType": "업태",
    "businessItem": "종목",
}


LABEL_ALIASES = {
    "등록번호": "businessRegistrationNumber",
    "사업자등록번호": "businessRegistrationNumber",
    "상호": "companyName",
    "상호(단체명등)": "companyName",
    "상호(단체명)": "companyName",
    "법인명": "companyName",
    "법인명(단체명)": "companyName",
    "대표자": "representativeName",
    "대표자명": "representativeName",
    "개업연월일": "openingDate",
    "개업일": "openingDate",
    "법인등록번호": "corporateRegistrationNumber",
    "사업장주소": "businessAddress",
    "사업장소재지": "businessAddress",
    "본점소재지": "headOfficeAddress",
    "업태": "businessType",
    "종목": "businessItem",
    "중목": "businessItem",
}


