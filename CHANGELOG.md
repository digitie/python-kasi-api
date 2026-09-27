# Changelog

## 미배포 — 비동기/TPS 전환

- KasiClient를 비동기 전용으로 통합하고 동기 facade/실행 스레드를 제거했다.
- debug와 페이지 순회를 await/async for로 이식하고 UI 사용 경계를 갱신했다.
- 공통 AsyncTokenBucket과 공유 rate_limiter를 추가해 재시도·redirect도 과금한다.

이 프로젝트의 사용자 가시적 변경 사항을 기록합니다. 형식은
[Keep a Changelog](https://keepachangelog.com/ko/1.1.0/)를 따릅니다.

## [Unreleased]

### Fixed

- 공휴일 등의 총건수에 정수만 허용하고 누락·불명확한 응답은 `None`으로 유지한다.
  fixture replay가 0이나 누락 총건수를 현재 행 수로 덮어쓰던 차이를 제거한다.

### Changed

- 저장소 문서 구성을 다른 `python-*-api` 형제 저장소와 동일한 규격으로 정리했습니다
  (README 구조, `AGENTS.md` 헤더, `docs/decisions.md` 도입, `LICENSE` 전문 추가).
