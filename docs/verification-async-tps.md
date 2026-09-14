# 비동기/TPS 전환 검증

- 독립 적대적 리뷰 2인 최종 승인. 공개 조회 16개·debug 16개와 namespace의 인자,
  공급자 파라미터·typed 모델·metadata 계약 보존을 비교했다.
- 오프라인 46개 및 14개 subtest 통과, Ruff/mypy/compileall 통과.
- 추가 검증: public/debug 공유 예산, 재시도/redirect, 취소 후 다음 대기자 진행,
  HTTP 본문 읽기 취소와 세션 종료, 오류 메시지/본문의 키 마스킹.
- live 4개 통과: 공휴일 조회 2개, 양력→음력 변환, 서울 출몰시각 조회. 실제 데이터의
  필드 값을 검증했다. HTTP 403은 발생하지 않았다.
