#!/usr/bin/env python3
"""Generate a 500-item life-oriented Korean practice sentence workbook.

The workbook keeps the existing import shape:
번호 / 난이도 / 카테고리 / 한국어 문장
"""

from __future__ import annotations

import argparse
import html
import zipfile
from pathlib import Path


ONSETS = [
    "ᄀ", "ᄁ", "ᄂ", "ᄃ", "ᄄ", "ᄅ", "ᄆ", "ᄇ", "ᄈ", "ᄉ",
    "ᄊ", "ᄋ", "ᄌ", "ᄍ", "ᄎ", "ᄏ", "ᄐ", "ᄑ", "ᄒ",
]
VOWELS = [
    "ᅡ", "ᅢ", "ᅣ", "ᅤ", "ᅥ", "ᅦ", "ᅧ", "ᅨ", "ᅩ", "ᅪ",
    "ᅫ", "ᅬ", "ᅭ", "ᅮ", "ᅯ", "ᅰ", "ᅱ", "ᅲ", "ᅳ", "ᅴ", "ᅵ",
]
CODAS = [
    None, "ᆨ", "ᆩ", "ᆪ", "ᆫ", "ᆬ", "ᆭ", "ᆮ", "ᆯ", "ᆰ",
    "ᆱ", "ᆲ", "ᆳ", "ᆴ", "ᆵ", "ᆶ", "ᆷ", "ᆸ", "ᆹ", "ᆺ",
    "ᆻ", "ᆼ", "ᆽ", "ᆾ", "ᆿ", "ᇀ", "ᇁ", "ᇂ",
]
NASALIZATION_CODAS = {"ᆨ", "ᆩ", "ᆪ", "ᆮ", "ᆺ", "ᆻ", "ᆽ", "ᆾ", "ᆿ", "ᇀ", "ᇂ", "ᆸ", "ᆹ", "ᇁ"}
OBSTRUENT_CODAS = NASALIZATION_CODAS
PLAIN_ONSETS = {"ᄀ", "ᄃ", "ᄇ", "ᄉ", "ᄌ"}
H_CODAS = {"ᆭ", "ᆶ", "ᇂ"}
PALATALIZATION_CODAS = {"ᆮ", "ᇀ"}
PALATALIZATION_VOWELS = {"ᅵ", "ᅧ"}
ASPIRATION_ONSETS = {"ᄀ", "ᄃ", "ᄇ", "ᄌ"}
ASPIRATION_CODAS = {"ᆨ", "ᆮ", "ᆸ", "ᆽ"}


def is_hangul_syllable(character: str) -> bool:
    return 0xAC00 <= ord(character) <= 0xD7A3


def decompose_syllable(character: str) -> tuple[str, str, str | None]:
    offset = ord(character) - 0xAC00
    onset_index = offset // 588
    vowel_index = (offset % 588) // 28
    coda_index = offset % 28
    return ONSETS[onset_index], VOWELS[vowel_index], CODAS[coda_index]


def hangul_units(text: str) -> list[tuple[str, str, str, str | None]]:
    return [
        (character, *decompose_syllable(character))
        for character in text
        if is_hangul_syllable(character)
    ]


def phonological_category(text: str) -> str | None:
    units = hangul_units(text)
    pairs = list(zip(units, units[1:], strict=False))

    if any(
        coda in PALATALIZATION_CODAS
        and next_onset == "ᄋ"
        and next_vowel in PALATALIZATION_VOWELS
        for (_, _, _, coda), (_, next_onset, next_vowel, _) in pairs
    ):
        return "구개음화"
    if any(
        coda in NASALIZATION_CODAS and next_onset in {"ᄂ", "ᄆ"}
        for (_, _, _, coda), (_, next_onset, _, _) in pairs
    ):
        return "비음화"
    if any(
        (coda == "ᆫ" and next_onset == "ᄅ") or (coda == "ᆯ" and next_onset == "ᄂ")
        for (_, _, _, coda), (_, next_onset, _, _) in pairs
    ):
        return "유음화"
    if any(
        (coda in H_CODAS and next_onset in ASPIRATION_ONSETS)
        or (coda in ASPIRATION_CODAS and next_onset == "ᄒ")
        for (_, _, _, coda), (_, next_onset, _, _) in pairs
    ):
        return "격음화"
    if any(
        coda in OBSTRUENT_CODAS and next_onset in PLAIN_ONSETS
        for (_, _, _, coda), (_, next_onset, _, _) in pairs
    ):
        return "경음화"
    if any(
        coda in H_CODAS and next_onset == "ᄋ"
        for (_, _, _, coda), (_, next_onset, _, _) in pairs
    ):
        return "ㅎ 탈락"
    if any(
        coda not in (None, "ᆼ", *H_CODAS) and next_onset == "ᄋ"
        for (_, _, _, coda), (_, next_onset, _, _) in pairs
    ):
        return "연음화"
    return None


SYLLABLES = (
    "가 나 다 라 마 바 사 아 자 차 카 타 파 하 "
    "개 내 대 래 매 배 새 애 재 채 캐 태 패 해 "
    "고 노 도 로 모 보 소 오 조 초 코 토 포 호 "
    "구 누 두 루 무 부 수 우 주 추 쿠 투 푸 후 "
    "기 니 디 리 미 비 시 이 지 치 키 티 피 히 "
    "강 남 달 말 밤 손 집 길 문 밥 물 약 열 숨 "
    "몸 눈 귀 입 목 발 힘 돈 값 병 원 역 "
    "학 교 일 책"
).split()


CATEGORIES = [
    {
        "name": "인사/대화",
        "syllables": "안 녕 하 세 요 네 예 아 니 괜 찮 감 사 죄 송".split(),
        "words": "안녕하세요 고맙습니다 죄송합니다 괜찮아요 반가워요 잠시만요 부탁해요 좋습니다 아니요 맞아요 천천히 다시 크게 작게 여기요".split(),
        "sentences": [
            "안녕하세요 만나서 반가워요",
            "고맙습니다 정말 도움이 됐어요",
            "죄송합니다 다시 말해 주세요",
            "괜찮아요 천천히 해도 돼요",
            "잠시만 기다려 주세요",
            "네 알겠습니다",
            "아니요 괜찮습니다",
            "다시 한번 말해 주세요",
            "조금 크게 말해 주세요",
            "천천히 말해 주세요",
            "제가 잘 못 들었어요",
            "이쪽으로 와 주세요",
            "먼저 말씀해 주세요",
            "나중에 다시 연락드릴게요",
            "오늘 기분이 좋아요",
            "내일 다시 만나요",
            "도와주셔서 감사합니다",
            "불편하면 바로 말할게요",
            "잠깐 쉬어도 될까요",
            "제 말을 확인해 주세요",
            "처음 뵙겠습니다 잘 부탁드립니다",
            "말이 빠르면 이해하기 어려워요",
            "중요한 내용은 다시 확인하고 싶어요",
            "제가 천천히 대답해도 괜찮을까요",
            "필요하면 글로 적어서 말씀드릴게요",
        ],
    },
    {
        "name": "요청/확인",
        "syllables": "도 와 주 좀 확 인 줘 볼 게 필 신 없 말 잠 깐".split(),
        "words": "도와주세요 확인해주세요 필요해요 필요없어요 보여주세요 알려주세요 적어주세요 기다려주세요 바꿔주세요 열어주세요 닫아주세요 찾아주세요 빌려주세요 확인할게요 괜찮습니다".split(),
        "sentences": [
            "도와주세요 길을 모르겠어요",
            "이 내용을 확인해 주세요",
            "종이에 적어 주실 수 있나요",
            "천천히 다시 알려 주세요",
            "화면을 보여 주세요",
            "문자를 보내 주세요",
            "잠깐만 기다려 주세요",
            "이름을 다시 확인할게요",
            "예약 내용을 확인하고 싶어요",
            "제가 이해한 게 맞나요",
            "다른 방법이 있나요",
            "이 버튼을 눌러도 되나요",
            "문을 열어 주세요",
            "조금 조용히 해 주세요",
            "가까이 와서 말해 주세요",
            "수어 통역이 필요해요",
            "필담으로 안내해 주세요",
            "전화 대신 문자로 연락해 주세요",
            "저는 천천히 말하면 이해할 수 있어요",
            "다시 한번 확인 부탁드립니다",
            "제가 요청한 내용을 순서대로 알려 주세요",
            "가능한 방법과 어려운 점을 같이 설명해 주세요",
            "확인한 내용을 문자로 남겨 주시면 좋겠습니다",
            "제가 이해한 내용을 다시 말해 보겠습니다",
            "필요한 서류가 더 있으면 적어 주세요",
        ],
    },
    {
        "name": "건강/응급",
        "syllables": "몸 야 처 병 료 열 숨 상 머 배 손 발 목 귀 코".split(),
        "words": "아파요 병원 약국 처방전 열나요 어지러워요 숨차요 다쳤어요 피나요 두통 복통 기침 감기 응급실 보호자".split(),
        "sentences": [
            "몸이 많이 아파요",
            "가까운 병원이 어디인가요",
            "약국에 가고 싶어요",
            "열이 나고 기침이 있어요",
            "숨쉬기가 조금 힘들어요",
            "머리가 아파요",
            "배가 아파요",
            "손을 다쳤어요",
            "피가 나요 도와주세요",
            "응급실로 가야 해요",
            "보호자에게 연락해 주세요",
            "진료 접수를 하고 싶어요",
            "약을 언제 먹어야 하나요",
            "물 한 컵 주세요",
            "알레르기가 있어요",
            "귀가 잘 들리지 않아요",
            "진료 내용을 천천히 설명해 주세요",
            "진료 내용을 문자로 보내 주세요",
            "보험증을 보여 드릴게요",
            "지금 바로 도움이 필요해요",
            "증상이 언제부터 시작됐는지 설명할게요",
            "복용 중인 약이 있어서 확인이 필요해요",
            "검사 결과를 쉬운 말로 설명해 주세요",
            "응급 상황이면 보호자에게 바로 연락해 주세요",
            "진료 후 주의할 점을 글로 적어 주세요",
        ],
    },
    {
        "name": "집/가족",
        "syllables": "집 방 문 창 밥 물 엄 마 부 빠 형 누 나 동 생".split(),
        "words": "우리집 가족 엄마 아빠 동생 침실 거실 부엌 화장실 열쇠 빨래 청소 전등 냉장고 쓰레기".split(),
        "sentences": [
            "집에 거의 다 왔어요",
            "문을 잠가 주세요",
            "열쇠를 어디에 두었나요",
            "방을 청소할게요",
            "빨래를 널어 주세요",
            "전등을 켜 주세요",
            "전등을 꺼 주세요",
            "냉장고에 물이 있어요",
            "가족에게 연락했어요",
            "엄마가 곧 오세요",
            "아빠에게 전화했어요",
            "동생을 데리러 가요",
            "화장실을 사용해도 될까요",
            "쓰레기를 버리고 올게요",
            "창문을 닫아 주세요",
            "밥을 같이 먹어요",
            "집 주소를 알려 드릴게요",
            "택배가 도착했어요",
            "오늘은 집에서 쉬고 싶어요",
            "문 앞에서 기다릴게요",
            "가스 밸브가 잠겼는지 확인해 주세요",
            "관리실에 수리 요청을 해야 해요",
            "가족 일정이 바뀌어서 다시 알려 드려요",
            "집에 손님이 오셔서 정리하고 있어요",
            "외출하기 전에 창문과 문을 확인할게요",
        ],
    },
    {
        "name": "식사/주문",
        "syllables": "죽 떡 식 반 찬 커 음 면 고 기 맛 뜨 거 냉 운".split(),
        "words": "식사 생수 국물 커피 음료 토스트 우유 라면 김밥 메뉴 주문 계산 포장 매워요 싱거워요".split(),
        "sentences": [
            "메뉴판을 보여 주세요",
            "물 한 잔 주세요",
            "이거 하나 주세요",
            "포장해 주세요",
            "여기서 먹고 갈게요",
            "계산해 주세요",
            "맵지 않게 해 주세요",
            "조금 싱겁게 해 주세요",
            "알레르기가 있어서 빼 주세요",
            "따뜻한 물이 필요해요",
            "커피 한 잔 주세요",
            "빵을 데워 주세요",
            "수저를 주세요",
            "반찬을 조금 더 주세요",
            "예약한 사람입니다",
            "자리 있나요",
            "화장실은 어디인가요",
            "영수증 주세요",
            "카드로 계산할게요",
            "맛있게 잘 먹었습니다",
            "음식에 들어간 재료를 확인하고 싶어요",
            "주문한 음식이 아직 나오지 않았어요",
            "소스는 따로 담아 주시면 좋겠습니다",
            "사람이 많아서 조용한 자리가 필요해요",
            "결제 전에 주문 내용을 다시 확인해 주세요",
        ],
    },
    {
        "name": "이동/교통",
        "syllables": "로 차 버 스 역 앞 뒤 좌 우 택 시 지 철 승 탄".split(),
        "words": "길안내 버스 지하철 택시 정류장 역사 출구 좌회전 우회전 직진 신호등 횡단보도 승차권 요금 도착".split(),
        "sentences": [
            "버스 정류장이 어디인가요",
            "지하철역으로 가고 싶어요",
            "택시를 불러 주세요",
            "여기서 내려 주세요",
            "다음 정류장에서 내려요",
            "몇 번 출구로 가야 하나요",
            "길을 잃었어요",
            "직진하면 되나요",
            "왼쪽으로 가면 되나요",
            "오른쪽으로 돌아가세요",
            "교통카드를 충전하고 싶어요",
            "요금이 얼마인가요",
            "도착하면 알려 주세요",
            "천천히 안내해 주세요",
            "횡단보도를 건너요",
            "신호를 기다려요",
            "가까운 길로 가 주세요",
            "주소를 보여 드릴게요",
            "기차 시간을 확인해 주세요",
            "길 안내를 문자로 보내 주세요",
            "환승해야 하는 곳을 미리 알려 주세요",
            "막차 시간을 놓치지 않게 확인해 주세요",
            "도착지가 가까워지면 문자로 알려 주세요",
            "길이 복잡하면 천천히 다시 안내해 주세요",
            "승강장 번호와 방향을 함께 확인해 주세요",
        ],
    },
    {
        "name": "쇼핑/결제",
        "syllables": "돈 값 카 드 현 금 봉 투 영 수 증 할 깎 교 환".split(),
        "words": "가격 카드 현금 결제 영수증 봉투 교환 환불 할인 사이즈 색깔 물건 계산대 찾아요 비싸요".split(),
        "sentences": [
            "이거 얼마인가요",
            "카드로 결제할게요",
            "현금으로 계산할게요",
            "영수증을 주세요",
            "봉투가 필요해요",
            "다른 색깔이 있나요",
            "큰 사이즈가 있나요",
            "작은 사이즈가 있나요",
            "교환하고 싶어요",
            "환불이 가능한가요",
            "할인 중인가요",
            "계산대가 어디인가요",
            "이 물건을 찾고 있어요",
            "가격표를 보여 주세요",
            "조금 비싸요",
            "포인트 적립할게요",
            "배송이 되나요",
            "결제 안내를 문자로 보내 주세요",
            "결제 방법을 천천히 설명해 주세요",
            "필요한 물건을 다 샀어요",
            "교환 기간과 필요한 영수증을 확인하고 싶어요",
            "배송 받을 주소를 다시 확인해 주세요",
            "결제 금액이 맞는지 화면으로 보여 주세요",
            "할인 적용 여부를 한번 더 확인해 주세요",
            "환불 절차를 글로 안내해 주시면 좋겠습니다",
        ],
    },
    {
        "name": "학교/직장",
        "syllables": "학 강 책 펜 글 회 의 업 숙 제 메 출 근 과 장".split(),
        "words": "학교 수업 선생님 친구 숙제 책상 직장 회의 메일 업무 출근 퇴근 자료 질문 발표".split(),
        "sentences": [
            "수업이 몇 시에 시작하나요",
            "숙제를 확인해 주세요",
            "선생님께 질문이 있어요",
            "친구와 같이 갈게요",
            "회의 시간이 바뀌었나요",
            "메일을 확인했습니다",
            "자료를 보내 주세요",
            "수업 내용을 천천히 설명해 주세요",
            "오늘 출근했습니다",
            "잠시 쉬어도 될까요",
            "일정을 다시 확인할게요",
            "발표 순서를 알려 주세요",
            "제가 먼저 말해도 될까요",
            "내용을 글로 남겨 주세요",
            "전화보다 메일이 편해요",
            "회의 내용을 문자로 보내 주세요",
            "도움이 필요하면 말씀드릴게요",
            "퇴근 후에 연락드릴게요",
            "같이 확인해 보면 좋겠습니다",
            "오늘 해야 할 일을 알려 주세요",
            "회의 내용을 문서로 공유해 주시면 좋겠습니다",
            "중요한 일정은 문자로 한번 더 알려 주세요",
            "발표할 때 천천히 말할 수 있도록 도와주세요",
            "업무 순서를 확인한 뒤 진행하겠습니다",
            "수업 자료를 미리 받아서 읽어 보고 싶어요",
        ],
    },
    {
        "name": "공공기관",
        "syllables": "구 청 은 행 공 체 관 경 찰 민 원 서 류 번 호".split(),
        "words": "구청 은행 우체국 경찰서 병무청 민원 서류 번호표 신분증 접수 창구 안내 주소 도장 신청".split(),
        "sentences": [
            "민원 접수를 하고 싶어요",
            "번호표를 뽑아야 하나요",
            "어느 창구로 가야 하나요",
            "신분증을 보여 드릴게요",
            "서류를 제출하러 왔어요",
            "주소를 변경하고 싶어요",
            "신청서를 작성할게요",
            "도장이 필요한가요",
            "은행 업무를 보러 왔어요",
            "계좌를 확인하고 싶어요",
            "우편을 보내고 싶어요",
            "등기 우편으로 보내 주세요",
            "경찰서에 신고하고 싶어요",
            "분실물을 찾고 있어요",
            "민원 안내를 문자로 보내 주세요",
            "필담으로 설명해 주세요",
            "수어 통역이 가능한가요",
            "대기 시간이 얼마나 되나요",
            "서류를 다시 확인해 주세요",
            "처리가 끝나면 알려 주세요",
            "접수 번호와 담당 창구를 다시 확인해 주세요",
            "필요한 서류 목록을 문자로 보내 주세요",
            "신청 결과를 언제 확인할 수 있나요",
            "수수료 결제 방법을 천천히 안내해 주세요",
            "안내 방송을 듣기 어려워서 직접 알려 주세요",
        ],
    },
    {
        "name": "감정/상태",
        "syllables": "좋 싫 힘 듦 곤 무 겁 불 편 슬 픔 느 낌 웃 울".split(),
        "words": "좋아요 싫어요 힘들어요 피곤해요 무서워요 불안해요 편해요 아쉬워요 슬퍼요 기뻐요 화나요 놀랐어요 졸려요 차분해요 답답해요".split(),
        "sentences": [
            "오늘은 기분이 좋아요",
            "조금 피곤해요",
            "몸이 무겁고 힘들어요",
            "마음이 불안해요",
            "지금은 쉬고 싶어요",
            "사람이 많아서 답답해요",
            "조용한 곳으로 가고 싶어요",
            "천천히 말하면 편해요",
            "갑자기 놀랐어요",
            "조금 무서워요",
            "도와주셔서 마음이 놓여요",
            "혼자 있고 싶어요",
            "같이 있어 주면 좋아요",
            "오늘은 말하기가 어려워요",
            "다시 해 보겠습니다",
            "칭찬해 주셔서 기뻐요",
            "실수해도 괜찮아요",
            "조금 더 연습하고 싶어요",
            "쉬면 나아질 것 같아요",
            "지금 상태를 설명하고 있어요",
            "말이 잘 안 나와도 기다려 주시면 좋겠어요",
            "오늘은 사람이 많은 곳이 조금 부담스러워요",
            "제가 표현하기 어려운 감정을 천천히 말해 볼게요",
            "실수해도 다시 시도할 수 있어서 괜찮아요",
            "도움을 받으니 마음이 조금 편해졌어요",
        ],
    },
]


def column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def inline_cell(reference: str, value: str | int) -> str:
    value = html.escape(str(value), quote=False)
    return f'<c r="{reference}" t="inlineStr"><is><t>{value}</t></is></c>'


def worksheet_xml(rows: list[list[str | int]]) -> str:
    xml_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = [
            inline_cell(f"{column_name(column_index)}{row_index}", value)
            for column_index, value in enumerate(row, start=1)
        ]
        xml_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(xml_rows)}</sheetData>'
        '</worksheet>'
    )


def workbook_files(rows: list[list[str | int]]) -> dict[str, str]:
    return {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '</Types>'
        ),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>'
        ),
        "xl/workbook.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="생활 연습문장 500" sheetId="1" r:id="rId1"/></sheets>'
            '</workbook>'
        ),
        "xl/_rels/workbook.xml.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '</Relationships>'
        ),
        "xl/worksheets/sheet1.xml": worksheet_xml(rows),
    }


def build_rows() -> list[list[str | int]]:
    rows: list[list[str | int]] = [["번호", "난이도", "카테고리", "한국어 문장"]]
    if len(SYLLABLES) != 100:
        raise ValueError(f"expected 100 beginner syllables, got {len(SYLLABLES)}")
    for text in SYLLABLES:
        rows.append([len(rows), "초급", "음절 연습", text])

    for category in CATEGORIES:
        if len(category["words"]) != 15:
            raise ValueError(f"{category['name']} must contain 15 words, got {len(category['words'])}")
        if len(category["sentences"]) != 25:
            raise ValueError(
                f"{category['name']} must contain 25 sentences, got {len(category['sentences'])}"
            )
        entries = (
            [("중급", text) for text in category["words"]]
            + [("상급", text) for text in category["sentences"][:15]]
            + [("심화", text) for text in category["sentences"][15:]]
        )
        if len(entries) != 40:
            raise ValueError(f"{category['name']} must contain 40 category entries, got {len(entries)}")
        for difficulty, text in entries:
            practice_category = phonological_category(text) or category["name"]
            rows.append([len(rows), difficulty, practice_category, text])
    texts = [row[3] for row in rows[1:]]
    duplicates = sorted({text for text in texts if texts.count(text) > 1})
    if duplicates:
        raise ValueError(f"duplicate texts: {duplicates}")
    if len(texts) != 500:
        raise ValueError(f"expected 500 texts, got {len(texts)}")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[3] / "korean_life_practice_sentences_500_v1.xlsx",
    )
    args = parser.parse_args()
    rows = build_rows()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w", compression=zipfile.ZIP_DEFLATED) as workbook:
        for name, content in workbook_files(rows).items():
            workbook.writestr(name, content)
    print(f"rows={len(rows) - 1}")
    print("life_categories=10")
    print("per_life_category=40")
    print("syllable_category=100")
    print("difficulties={'초급': 100, '중급': 150, '상급': 150, '심화': 100}")
    print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
