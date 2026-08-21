# 🎥 Food Shorts 자동 생성 설정 가이드

## 📍 생성된 영상 위치

모든 자동 생성된 영상과 파일은 **이 경로**에 저장됩니다:
```
/home/user/Soop1230/food_shorts/output/generated/
```

### 파일 구성
각 생성마다 다음 4개 파일이 생성됩니다:
- `food_YYYYMMDD_HHMMSS.mp4` ← **YouTube 업로드할 영상 파일**
- `food_YYYYMMDD_HHMMSS_metadata.json` ← **YouTube 제목/설명/태그 정보**
- `food_YYYYMMDD_HHMMSS_bg.png` ← 배경 이미지 (삭제 가능)
- `food_YYYYMMDD_HHMMSS_audio.mp3` ← 오디오 파일 (삭제 가능)

---

## ⚙️ Step 1: PC에서 Cron 자동 실행 설정

### macOS / Linux 사용자

터미널을 열고 다음 명령어 실행:
```bash
crontab -e
```

텍스트 편집기가 열리면, 맨 아래에 다음 라인을 추가:
```
0 9,15,18,21 * * * cd /home/user/Soop1230/food_shorts/scripts && python3 generate_video.py >> /home/user/Soop1230/food_shorts/output/logs/cron.log 2>&1
```

**설명:**
- `0 9,15,18,21 * * *` = 매일 09:00, 15:00, 18:00, 21:00에 실행 (KST)
- 저장: 에디터 종료 (Vim: `:wq` + Enter, Nano: Ctrl+X → Y → Enter)

### Windows 사용자

작업 스케줄러(Task Scheduler)에서:
1. 새 작업 만들기
2. 트리거: 반복 (09:00, 15:00, 18:00, 21:00)
3. 작업: 
   ```
   프로그램: python3
   인수: /home/user/Soop1230/food_shorts/scripts/generate_video.py
   시작 위치: /home/user/Soop1230/food_shorts/scripts
   ```

---

## ✅ Step 2: Cron 설정 확인

설정이 잘 되었는지 확인하려면:
```bash
crontab -l
```

위에서 추가한 라인이 나타나면 설정 완료!

---

## 🔍 Step 3: 생성 로그 확인

자동 생성이 제대로 되는지 모니터링하려면:
```bash
tail -f /home/user/Soop1230/food_shorts/output/logs/cron.log
```

또는 파일 브라우저에서:
```
/home/user/Soop1230/food_shorts/output/logs/cron.log
```

로그 파일을 더블클릭해서 열면 생성 기록을 볼 수 있습니다.

---

## 📤 Step 4: YouTube에 수동 업로드

### 4-1. 생성된 영상 찾기

파일 브라우저 열기 → 주소창에 다음 입력:
```
/home/user/Soop1230/food_shorts/output/generated/
```

또는 단축키: Ctrl+L 후 위의 경로 붙여넣기

### 4-2. 최신 영상 선택

**생성 시간 기준 최신 순**으로 정렬:
- Windows: "수정한 날짜" 클릭
- Mac: "수정일" 클릭

가장 위의 `food_YYYYMMDD_HHMMSS.mp4` 파일이 최신입니다.

### 4-3. 메타데이터 확인

같은 폴더에서 `food_YYYYMMDD_HHMMSS_metadata.json` 파일 우클릭 → "연결 프로그램" → 메모장으로 열기

내용:
```json
{
  "title": "영상 제목",
  "description": "영상 설명\n\n🛒 Coupang 링크\n\n구독 감사합니다!",
  "tags": ["#태그1", "#태그2"]
}
```

### 4-4. YouTube Studio에 업로드

1. https://studio.youtube.com 열기
2. "동영상 업로드" 클릭
3. `food_YYYYMMDD_HHMMSS.mp4` 파일 선택
4. 메타데이터 입력:
   - **제목**: metadata.json의 `"title"` 값 복사-붙여넣기
   - **설명**: metadata.json의 `"description"` 값 복사-붙여넣기
   - **태그**: metadata.json의 `"tags"` 배열 값들을 쉼표로 구분해서 입력
   - **분류**: 엔터테인먼트 또는 교육
5. 공개/비공개 선택 → 업로드

---

## 📊 자동 생성 일정

Cron 설정 후, 아래 시간에 자동으로 영상이 생성됩니다:
- ✅ 09:00 (오전 9시)
- ✅ 15:00 (오후 3시)
- ✅ 18:00 (오후 6시)
- ✅ 21:00 (오후 9시)

---

## 🧪 테스트: 수동으로 영상 생성해보기

바로 테스트하고 싶으면:
```bash
cd /home/user/Soop1230/food_shorts/scripts
python3 generate_video.py
```

실행 완료 후 생성 폴더 확인:
```bash
ls -lh /home/user/Soop1230/food_shorts/output/generated/
```

최신 파일이 생성되었는지 확인하세요.

---

## ⚠️ 주의사항

1. **Python & ffmpeg 설치 확인**
   ```bash
   python3 --version
   ffmpeg -version
   ```
   
   설치 안 되어 있으면:
   - **macOS**: `brew install python3 ffmpeg`
   - **Linux**: `sudo apt-get install python3 ffmpeg`
   - **Windows**: https://www.python.org, https://ffmpeg.org 에서 다운로드

2. **한글 폰트 설치** (영상 제목 표시용)
   - **macOS**: 기본 설치됨
   - **Linux**: `sudo apt-get install fonts-noto-cjk`
   - **Windows**: 기본 설치됨

3. **네트워크 연결**
   - TTS(음성 생성)를 위해 인터넷 연결 필요
   - 오프라인 상태에서는 영상이 음성 없이 생성됨 (정상 작동)

---

## 📝 자주 묻는 질문

### Q: 생성된 영상은 어디에 있나요?
→ `/home/user/Soop1230/food_shorts/output/generated/`

### Q: Cron이 제대로 작동하는지 확인하려면?
→ 로그 파일 확인: `/home/user/Soop1230/food_shorts/output/logs/cron.log`

### Q: 영상이 생성 안 되면?
→ 로그 파일 확인해서 에러 메시지 보기

### Q: YouTube에 수동으로 업로드하는 방법?
→ 위의 "Step 4: YouTube에 수동 업로드" 참고

### Q: 생성 시간을 바꾸고 싶으면?
→ `crontab -e` 열어서 `0 9,15,18,21` 부분 수정 (24시간 형식)

---

## 🎉 설정 완료!

Cron 설정이 완료되면, 더 이상 할 일이 없습니다.
매일 자동으로 영상이 생성되고, 생성 파일을 YouTube에 수동으로 업로드하면 끝!

궁금한 점이 있으면 로그 파일을 먼저 확인하세요.
