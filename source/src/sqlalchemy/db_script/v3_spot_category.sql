-- v3: 테마파크를 따로 두지 않고 관광지("가볼만한 곳")로 통합. 세부 종류는 type(네이버 업종) 마지막 단계로 구분
UPDATE place SET category = '관광지' WHERE category = '테마파크';
