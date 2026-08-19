import librosa
import numpy as np
from typing import Dict


class AudioAnalyzer:
    """오디오 분석 및 AI 자동 프리셋 추천"""

    def __init__(self):
        self.sr = 22050

    def analyze(self, audio_path: str) -> Dict:
        """오디오 파일 분석"""
        try:
            y, sr = librosa.load(audio_path, sr=self.sr)

            # BPM 감지
            bpm = self._extract_bpm(y, sr)

            # 키 감지
            key = self._extract_key(y, sr)

            # 에너지 레벨
            energy = self._extract_energy(y)

            # 장르 추론
            genre = self._infer_genre(y, sr, bpm, energy)

            # 추천 프리셋
            preset = self._recommend_preset(bpm, energy, genre)

            return {
                "bpm": round(bpm, 1),
                "key": key,
                "energy": round(energy, 2),
                "genre": genre,
                "recommended_preset": preset,
                "analysis_details": {
                    "duration": round(len(y) / sr, 2),
                    "sample_rate": sr,
                    "confidence": "높음" if energy > 0.4 else "중간"
                }
            }
        except Exception as e:
            return {
                "error": str(e),
                "recommended_preset": "감성"  # 기본값
            }

    def _extract_bpm(self, y: np.ndarray, sr: int) -> float:
        """BPM 추출"""
        try:
            onset_env = librosa.onset.onset_strength(y=y, sr=sr)
            bpm = librosa.beat.tempo(onset_envelope=onset_env, sr=sr)[0]
            return float(bpm)
        except:
            return 90.0  # 기본값

    def _extract_key(self, y: np.ndarray, sr: int) -> str:
        """키 감지"""
        try:
            chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
            chroma_mean = np.mean(chroma, axis=1)
            key_idx = np.argmax(chroma_mean)

            keys = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
            return keys[key_idx]
        except:
            return "C"  # 기본값

    def _extract_energy(self, y: np.ndarray) -> float:
        """에너지 레벨 추출"""
        try:
            rms = np.sqrt(np.mean(y ** 2))
            return float(rms)
        except:
            return 0.5  # 기본값

    def _infer_genre(self, y: np.ndarray, sr: int, bpm: float, energy: float) -> str:
        """장르 추론"""
        if 85 <= bpm <= 110:
            if energy > 0.5:
                return "활력힙합"
            else:
                return "감성힙합"
        elif bpm > 110:
            return "빠른비트"
        else:
            return "슬로우"

    def _recommend_preset(self, bpm: float, energy: float, genre: str) -> str:
        """음악 특성에 따른 프리셋 추천"""
        if energy < 0.3:
            return "감성"
        elif energy > 0.6 and bpm > 100:
            return "활력"
        elif "래퍼" in genre or "보컬" in genre:
            return "보컬"
        elif bpm < 80:
            return "감성"
        else:
            return "클래식"
