import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from molit_fetcher import extract_jibun, _jibun_match


class TestExtractJibun:
    """onbid_cltr_nm / zadr_nm에서 지번을 추출한다."""

    def test_basic_jibun_with_bunji(self):
        assert extract_jibun("인천 미추홀구 숭의동 302-8 외 4필지 숭의엠타운 903호") == "302-8"

    def test_basic_jibun_without_bunji(self):
        assert extract_jibun("서울특별시 송파구 거여동 604-3 아피체 제1층 제111호") == "604-3"

    def test_jibun_with_oe_pilji(self):
        assert extract_jibun("서울특별시 서초구 서초동 1302-1 외 2필지, 214호 업무시설") == "1302-1"

    def test_jibun_no_bubon(self):
        assert extract_jibun("경기도 여주시 오학동 292 그랑시티 제102동") == "292"

    def test_ri_address(self):
        assert extract_jibun("경기도 양주시 광적면 덕도리 123-4 건물") == "123-4"

    def test_ga_address(self):
        assert extract_jibun("서울특별시 중구 을지로1가 55-2 빌딩") == "55-2"

    def test_zadr_nm_priority(self):
        result = extract_jibun(
            "무관한 텍스트",
            zadr_nm="서울특별시 송파구 거여동 604-3 아피체 제1층"
        )
        assert result == "604-3"

    def test_none_input(self):
        assert extract_jibun(None) is None

    def test_no_match(self):
        assert extract_jibun("알 수 없는 물건명") is None

    def test_brackets_in_name(self):
        assert extract_jibun("울산 남구 신정동 1222-7 [신정반트펠리시아] 제6층") == "1222-7"


class TestJibunMatch:
    """지번 매칭 규칙 테스트."""

    def test_exact_match(self):
        assert _jibun_match("302-8", "302-8") is True

    def test_bonbun_match(self):
        assert _jibun_match("302-8", "302") is True

    def test_reverse_bonbun_match(self):
        assert _jibun_match("302", "302-8") is True

    def test_different_bonbun(self):
        assert _jibun_match("302-8", "303-1") is False

    def test_none_a(self):
        assert _jibun_match(None, "302-8") is False

    def test_none_b(self):
        assert _jibun_match("302-8", None) is False

    def test_both_none(self):
        assert _jibun_match(None, None) is False

    def test_empty_string(self):
        assert _jibun_match("", "302-8") is False

    def test_same_bonbun_different_bubun(self):
        assert _jibun_match("302-8", "302-3") is True
