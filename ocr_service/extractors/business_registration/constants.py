"""사업자등록증 파싱에 쓰는 고정 라벨과 키워드를 정의한다."""

REQUIRED_BUSINESS_FIELDS = {
    "businessRegistrationNumber": "사업자등록번호",
    "companyName": "상호(단체명 등)",
    "representativeName": "대표자명",
    "openingDate": "개업연월일",
    "businessAddress": "사업장주소",
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


HIGH_CONFIDENCE_ADVERTISING_KEYWORDS = (
    "광고대행",
    "광고기획",
    "광고제작",
    "광고물",
    "옥외광고",
    "전시광고",
    "온라인광고",
    "검색광고",
    "바이럴",
    "매체대행",
    "판촉",
    "판촉물",
    "광고",
)


MEDIUM_CONFIDENCE_ADVERTISING_KEYWORDS = (
    "마케팅대행",
    "홍보대행",
    "프로모션",
    "브랜딩",
    "콘텐츠마케팅",
    "sns마케팅",
    "마케팅",
    "홍보",
)
