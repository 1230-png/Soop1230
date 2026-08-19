# 새벽공기 (Dawn Air) — Suno 감성 힙합 플레이리스트 채널

Suno로 제작하는 한국어 감성 힙합 / R&B 플레이리스트 채널. 프로덕션 워크플로우는
`3am-suno-batch` 스킬(배치 설계 → 가사/Suno 프롬프트 → 결과 기록)을 기반으로 운영한다.

## 채널 정체성 (Style 앵커)

```
Korean mood hip-hop, R&B hip-hop, singing rap, late night city vibe,
breathy male vocal, restrained emotion, clear diction, natural phrasing,
American English pronunciation on chorus
```

기본 보컬은 breathy / restrained. 배치당 2~3곡의 "변주 슬롯"에서만
`confident male vocal, open emotional delivery`로 완화해 도시 드라이브 · 위로 ·
활력 곡을 표현한다 (나머지 7개 앵커 요소는 항상 유지).

## 운영 파일

- `song_log.csv` — 발매곡 기록(중복 방지, 밸런스 체크용). Suno 생성 결과가 나올 때마다 기록.
- `batch_01.md` — 1차 배치 10곡 설계 + 가사 + Style/Exclude 프롬프트.

## 다음 단계 (제작 이후)

1. `batch_01.md`의 각 곡을 Suno에 Style/Exclude/Lyrics 그대로 입력해 생성
2. 결과(실제 BPM, 길이, 품질)를 알려주면 실패 코드 판정 → 필요 시 1개 파라미터만 바꿔 재생성(곡당 최대 3회)
3. 확정된 곡은 `song_log.csv`에 기록
4. 업로드용 커버 이미지 / 플레이리스트 영상(정적 이미지 + 오디오, 또는 루프 비주얼) 제작
5. 제목/설명/태그 SEO, 업로드 스케줄 정리 — 이 부분은 이후 별도로 도와드릴 수 있음
