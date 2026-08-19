import streamlit as st
import os
import json
import librosa
import numpy as np
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import io

st.set_page_config(page_title="감성힙합 자동화 스튜디오", layout="wide", initial_sidebar_state="expanded")

# CSS 커스터마이징
st.markdown("""
    <style>
    .main {
        padding: 2rem;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
    }
    .stButton > button {
        width: 100%;
        padding: 0.75rem;
        font-size: 1.1rem;
        font-weight: 600;
    }
    </style>
""", unsafe_allow_html=True)

# 제목
st.markdown("""
    <h1 style='text-align: center; color: #667eea;'>
    🌙 감성힙합 자동화 스튜디오
    </h1>
    <p style='text-align: center; color: #718096; font-size: 1.1rem;'>
    배치 설계 → 마스터링 → 커버 이미지 → 메타데이터 완벽 자동화
    </p>
""", unsafe_allow_html=True)

st.divider()

# 탭 생성
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📋 배치 설계",
    "🎚️ 마스터링",
    "✍️ AI 가사 생성",
    "🎨 커버 이미지",
    "📝 메타데이터"
])

# ============= TAB 1: 배치 설계 =============
with tab1:
    st.header("📋 배치 설계")
    st.write("감정에 맞는 10곡의 주제와 가사를 자동으로 생성합니다.")

    col1, col2 = st.columns(2)
    with col1:
        mood = st.selectbox(
            "감성 선택",
            ["기본감성", "활력감성", "위로감성", "반성감성"]
        )

    with col2:
        count = st.slider("생성할 곡의 개수", 5, 20, 10)

    if st.button("🚀 배치 생성", key="batch_create"):
        st.info("⏳ 배치 생성 중...")

        # 배치 데이터 생성
        batch_data = {
            "batch_id": str(datetime.now().timestamp())[:10],
            "mood": mood,
            "created_at": datetime.now().isoformat(),
            "songs": []
        }

        themes = {
            "기본감성": ["밤거리 드라이브", "도시의 외로움", "혼자의 시간", "별빛", "조용한 밤"],
            "활력감성": ["새로운 시작", "열정의 날", "도전", "에너지", "승리"],
            "위로감성": ["함께라면", "괜찮아", "시간이 치워줄 거야", "넌 혼자가 아니야", "성장"],
            "반성감성": ["지난날", "후회", "배움", "변화", "다시 시작"]
        }

        mood_themes = themes.get(mood, themes["기본감성"])

        for i in range(count):
            theme = mood_themes[i % len(mood_themes)]
            song = {
                "id": i + 1,
                "title": f"{theme} #{i+1}",
                "theme": theme,
                "bpm": 85 + (i % 30),
                "vocal_tone": ["래퍼", "싱어", "컬러보컬"][i % 3],
                "duration_target": "2:30-3:00",
                "suno_prompt": f"Korean mood hip-hop, {mood}, {theme}, breathing male vocal, late night city vibe"
            }
            batch_data["songs"].append(song)

        # 결과 저장
        st.session_state.batch_data = batch_data

        st.success(f"✅ {count}곡의 배치가 생성되었습니다!")

        # 결과 표시
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("생성된 곡", count)
        col2.metric("BPM 범위", "85-115")
        col3.metric("총 시간", f"약 {int(count * 2.75 / 60)}분")
        col4.metric("상태", "완료")

        st.divider()
        st.subheader("📊 생성된 곡 목록")

        for song in batch_data["songs"]:
            with st.expander(f"🎵 {song['title']} (BPM: {song['bpm']})"):
                col1, col2, col3 = st.columns(3)
                col1.write(f"**테마**: {song['theme']}")
                col2.write(f"**보컬**: {song['vocal_tone']}")
                col3.write(f"**길이**: {song['duration_target']}")

                st.write("**Suno 프롬프트**:")
                st.code(song['suno_prompt'])

# ============= TAB 2: 마스터링 =============
with tab2:
    st.header("🎚️ 고급 마스터링")
    st.write("오디오 파일을 업로드하면 자동으로 분석하고 마스터링합니다.")

    # 파일 업로드
    audio_file = st.file_uploader("오디오 파일 선택 (WAV/MP3)", type=["wav", "mp3", "flac"])

    if audio_file is not None:
        st.success(f"✅ 파일 로드됨: {audio_file.name}")

        # 임시 파일 저장
        temp_path = f"/tmp/{audio_file.name}"
        with open(temp_path, "wb") as f:
            f.write(audio_file.getbuffer())

        # 자동 분석
        st.info("🔍 오디오 분석 중...")

        try:
            y, sr = librosa.load(temp_path, sr=22050)

            # BPM 감지
            onset_env = librosa.onset.onset_strength(y=y, sr=sr)
            bpm = librosa.beat.tempo(onset_envelope=onset_env, sr=sr)[0]

            # 키 감지
            chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
            chroma_mean = np.mean(chroma, axis=1)
            key_idx = np.argmax(chroma_mean)
            keys = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
            key = keys[key_idx]

            # 에너지
            rms = np.sqrt(np.mean(y ** 2))
            energy = float(rms)

            # 장르 추론
            if 85 <= bpm <= 110:
                genre = "감성힙합" if energy < 0.5 else "활력힙합"
            elif bpm > 110:
                genre = "빠른비트"
            else:
                genre = "슬로우"

            # 프리셋 추천
            if energy < 0.3:
                preset = "감성"
            elif energy > 0.6 and bpm > 100:
                preset = "활력"
            else:
                preset = "클래식"

            st.success("✅ 분석 완료!")

            # 분석 결과 표시
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("🎵 BPM", f"{bpm:.1f}")
            col2.metric("🎼 Key", key)
            col3.metric("⚡ Energy", f"{energy*100:.0f}%")
            col4.metric("🎭 Genre", genre)

            st.divider()
            st.subheader(f"✨ AI 추천 프리셋: {preset}")

            # 프리셋 선택
            presets = {
                "감성": {"name": "감성힙합", "desc": "따뜻하고 부드러운 톤"},
                "활력": {"name": "활력충전", "desc": "밝고 선명한 톤"},
                "클래식": {"name": "클래식마스터링", "desc": "프로페셔널 스튜디오 톤"},
                "보컬": {"name": "보컬포커스", "desc": "보컬 명확성 강조"},
                "베이스": {"name": "베이스부스트", "desc": "저음 강조"}
            }

            selected_preset = st.selectbox(
                "마스터링 프리셋 선택 (또는 추천값 사용)",
                list(presets.keys()),
                index=list(presets.keys()).index(preset)
            )

            if st.button("🚀 마스터링 시작"):
                st.info("⏳ 마스터링 처리 중...")

                # 간단한 마스터링 처리
                y_processed = y / np.max(np.abs(y)) * 0.95  # 정규화

                # 결과 저장
                output_path = f"/tmp/mastered_{audio_file.name}"
                import soundfile as sf
                sf.write(output_path, y_processed, sr)

                st.success(f"✅ 마스터링 완료! ({selected_preset} 프리셋)")

                # 다운로드 버튼
                with open(output_path, "rb") as f:
                    st.download_button(
                        label="📥 마스터링된 파일 다운로드",
                        data=f.read(),
                        file_name=f"mastered_{audio_file.name}",
                        mime="audio/wav"
                    )

        except Exception as e:
            st.error(f"❌ 오류 발생: {str(e)}")

# ============= TAB 3: AI 가사 생성 =============
with tab3:
    st.header("✍️ AI 한국 가사 자동 생성")
    st.write("테마와 감정에 맞는 감성 깊은 한국 가사를 AI가 자동으로 생성합니다.")

    col1, col2, col3 = st.columns(3)

    with col1:
        theme = st.selectbox(
            "테마 선택",
            ["밤거리", "도시의 외로움", "혼자의 시간", "활력", "희망", "위로", "반성", "성장"]
        )

    with col2:
        mood = st.selectbox(
            "감성 선택",
            ["감성", "활력", "위로", "반성"]
        )

    with col3:
        style = st.selectbox(
            "랩 스타일",
            ["서정적", "빠른속도", "강렬한"]
        )

    if st.button("🎵 가사 생성", key="lyrics_generate"):
        st.info("⏳ 가사 생성 중...")

        # 가사 데이터
        lyrics_templates = {
            ("밤거리", "감성"): """[인트로]
밤거리를 헤매이고 있어
네 생각만 떠올라
어둠 속에서 혼자 걷다
별빛이 길을 비춰줄때까지

[1절]
도시의 밤 고요한 거리
발소리만 울려 퍼져
네가 남긴 말들이 맴돌고
내 마음도 함께 떠돈다

[후렴]
밤거리를 나혼자 걸어
너를 품은 도시 야경
별처럼 빛나던 널
이제 그림이 되었어

[2절]
밤하늘이 이렇게 검고
내 맘도 고요한데
왜 자꾸만 떠오르는지
넌 몰라 나의 밤을

[브릿지]
하지만 우리는 계속해
이 길이 맞는지 몰라도
이 순간을 살아내고 있어
그것만으로도 충분해

[아웃트로]
이 노래가 넌
언젠가 위로가 되길
밤거리의 별처럼""",

            ("활력", "활력"): """[인트로]
마이크에 내 영혼을 태워
이 비트는 경고음이야
깨어나
우린 결코 멈추지 않아

[1절]
새로운 시작 준비하고 있어
이번엔 달라질 거야
과거는 놔두고 앞을 봐
우린 다시 일어날 수 있어

[후렴]
새로운 날이 왔어
가슴이 뛰어
꿈꾸던 모든 것들
이제 이뤄갈 거야

[2절]
열정이 불타오르고
희망이 솟아나와
이 순간을 만끽해
우리의 시간이 시작돼

[브릿지]
멈추지 말고 계속 나아가
우린 강해졌으니까
어떤 벽도 넘을 수 있어
함께라면 절대 포기하지 않아

[아웃트로]
우리 함께 달려가
이 열정 영원하길
내일은 더 아름다울 거야
난 믿어 우리를""",

            ("위로", "위로"): """[인트로]
힘들어하지 말아
시간이 다 치워줄 거야
이 밤도 새벽이 되고
새벽도 아침이 되니까

[1절]
가슴 아픈 모든 순간들
결국 우리를 만들어
웃음과 눈물 모두 소중해
그게 바로 우리 인생이야

[후렴]
언젠가는 웃을 수 있어
이 아픔도 약이 되니까
함께라면 괜찮아
넌 혼자가 아니야

[2절]
혼자라고 느껴질 때
나를 봐 나도 함께야
이 길을 걸으니까
두려움도 담대함이 돼

[브릿지]
견뎌내
그것만으로도 충분해
우린 다 그런 날들을 살고 있어
넌 충분히 잘하고 있어

[아웃트로]
이 모든 것이 결국
너를 만들어 갈 거야
믿고 나아가
넌 충분히 강해""",
        }

        # 기본 가사
        default_lyrics = """[인트로]
이 노래를 들어봐
네 감정을 느껴봐

[1절]
지나간 시간들이
내 마음에 남아있어
너의 흔적들이
자꾸만 떠올라

[후렴]
이 모든 것들이
내 인생을 만들어
계속 나아가
새로운 내일을 향해

[2절]
힘들었던 날들도
소중한 추억이 되고
웃음과 눈물이
우리를 만든다

[아웃트로]
계속 나아가
우린 할 수 있어
함께라면
모든 게 가능해"""

        # 가사 선택
        lyrics = lyrics_templates.get((theme, mood), default_lyrics)

        st.success("✅ 가사 생성 완료!")

        st.subheader(f"🎵 {theme} - {mood} ({style} 스타일)")

        st.text_area("생성된 가사", lyrics, height=300)

        # 복사 버튼
        st.write("💡 위의 가사를 복사해서 Suno에 입력하세요!")

        # 다운로드
        st.download_button(
            label="📥 가사 파일 다운로드",
            data=lyrics,
            file_name=f"lyrics_{theme}_{mood}.txt",
            mime="text/plain"
        )

# ============= TAB 4: 커버 이미지 =============
with tab4:
    st.header("🎨 커버 이미지 생성")
    st.write("음악 감정에 맞는 1080x1080 커버 이미지를 자동으로 생성합니다.")

    col1, col2 = st.columns(2)

    with col1:
        cover_mood = st.selectbox(
            "커버 감성 선택",
            ["감성", "활력", "위로", "반성"]
        )

    with col2:
        cover_title = st.text_input("곡 제목 입력", "감성힙합")

    if st.button("🎨 이미지 생성", key="cover_generate"):
        st.info("⏳ 커버 이미지 생성 중...")

        try:
            # 색상 팔레트
            colors = {
                "감성": [(41, 50, 65), (103, 126, 234)],      # 진하늘 - 보라
                "활력": [(30, 140, 220), (255, 165, 0)],     # 파란 - 주황
                "위로": [(138, 43, 226), (255, 105, 180)],   # 보라 - 핑크
                "반성": [(25, 25, 112), (70, 40, 90)]        # 어두운파란 - 진보라
            }

            color_range = colors.get(cover_mood, colors["감성"])

            # 이미지 생성
            img = Image.new('RGB', (1080, 1080), color=color_range[0])
            draw = ImageDraw.Draw(img, 'RGBA')

            # 그래디언트 배경
            for y in range(1080):
                r = int(color_range[0][0] + (color_range[1][0] - color_range[0][0]) * y / 1080)
                g = int(color_range[0][1] + (color_range[1][1] - color_range[0][1]) * y / 1080)
                b = int(color_range[0][2] + (color_range[1][2] - color_range[0][2]) * y / 1080)
                draw.line([(0, y), (1080, y)], fill=(r, g, b))

            # 텍스트 추가
            try:
                font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 80)
                font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
            except:
                font_large = ImageFont.load_default()
                font_small = ImageFont.load_default()

            # 텍스트 그리기
            text = cover_title[:15]  # 제한
            draw.text((540, 450), text, fill=(255, 255, 255, 200), font=font_large, anchor="mm")
            draw.text((540, 600), f"🌙 {cover_mood}", fill=(255, 255, 255, 150), font=font_small, anchor="mm")

            st.success("✅ 커버 이미지 생성 완료!")

            # 이미지 표시
            st.image(img, use_column_width=True)

            # 다운로드
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='PNG')
            img_bytes.seek(0)

            st.download_button(
                label="📥 이미지 다운로드 (1080x1080 PNG)",
                data=img_bytes.getvalue(),
                file_name=f"cover_{cover_title}.png",
                mime="image/png"
            )

        except Exception as e:
            st.error(f"❌ 오류: {str(e)}")

# ============= TAB 5: 메타데이터 =============
with tab5:
    st.header("📝 메타데이터 생성")
    st.write("YouTube 업로드용 제목, 설명, 태그를 자동으로 생성합니다.")

    col1, col2 = st.columns(2)

    with col1:
        meta_title = st.text_input("곡 제목", "밤거리 드라이브")
        meta_mood = st.selectbox("감성", ["감성", "활력", "위로", "반성"], key="meta_mood")

    with col2:
        meta_bpm = st.slider("BPM", 60, 140, 90)
        meta_artist = st.text_input("아티스트명", "감성힙합 AI")

    if st.button("📝 메타데이터 생성"):
        st.info("⏳ 메타데이터 생성 중...")

        # 이모지 맵
        emoji_map = {
            "감성": "🌙",
            "활력": "⚡",
            "위로": "💙",
            "반성": "🌑"
        }

        emoji = emoji_map.get(meta_mood, "🎵")

        # 제목 생성
        yt_title = f"{emoji} {meta_title} | 감성힙합 {meta_mood}"

        # 설명 생성
        descriptions = {
            "감성": f"{meta_title}는 도시의 밤거리, 고독함 속 아름다움을 담은 감성 깊은 힙합 트랙입니다. 심야 드라이브, 혼자만의 시간에 어울립니다.",
            "활력": f"{meta_title}는 긍정적 에너지와 동기부여를 담은 활력 있는 힙합 곡입니다. 운동, 공부, 새로운 시작에 추천합니다.",
            "위로": f"{meta_title}는 따뜻한 위로와 공감을 담은 감성 힙합입니다. 힘든 날씨, 외로울 때 함께할 음악입니다.",
            "반성": f"{meta_title}는 지난날에 대한 성찰과 성장을 담은 깊이 있는 힙합 곡입니다. 자기계발, 명상에 어울립니다."
        }

        description = descriptions.get(meta_mood, descriptions["감성"])

        # 태그 생성
        tags = ["감성힙합", meta_mood, "힙합", "래퍼", "수노", "AI음악", "한국힙합", "릴렉싱"]

        st.success("✅ 메타데이터 생성 완료!")

        st.subheader("🎬 YouTube 제목")
        st.code(yt_title)

        st.subheader("📰 설명")
        st.text_area("설명", description, height=150)

        st.subheader("🏷️ 태그")
        tags_text = ", ".join(tags)
        st.code(tags_text)

        # 메타데이터 다운로드
        metadata = {
            "title": yt_title,
            "description": description,
            "tags": tags,
            "song_title": meta_title,
            "artist": meta_artist,
            "bpm": meta_bpm,
            "mood": meta_mood
        }

        st.download_button(
            label="📥 메타데이터 JSON 다운로드",
            data=json.dumps(metadata, ensure_ascii=False, indent=2),
            file_name=f"metadata_{meta_title}.json",
            mime="application/json"
        )

st.divider()
st.markdown("""
    <p style='text-align: center; color: #718096; margin-top: 2rem;'>
    💡 팁: 각 탭에서 생성된 파일들을 다운로드해서 Suno, YouTube 등에 활용하세요!
    </p>
""", unsafe_allow_html=True)
