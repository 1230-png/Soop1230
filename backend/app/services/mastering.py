import librosa
import numpy as np
from scipy import signal
import soundfile as sf
from typing import Tuple


class MasteringEngine:
    """고급 마스터링 엔진"""

    def __init__(self):
        self.sr = 44100
        self.loudness_target = -14.0  # LUFS

    def process(self, input_path: str, output_path: str) -> dict:
        """전체 마스터링 처리"""
        try:
            # 1. 오디오 로드
            y, sr = librosa.load(input_path, sr=self.sr)

            # 2. 클립핑 감지 및 정규화
            y = self._soft_clip(y)

            # 3. 고급 EQ (멀티밴드)
            y = self._multiband_eq(y, sr)

            # 4. 동적 범위 처리 (압축)
            y = self._compression(y)

            # 5. 스테레오 처리 (모노 신호를 스테레오로 확장)
            y_stereo = self._stereo_enhancement(y)

            # 6. 마스터링 체인 (제한기 + 정규화)
            y_stereo = self._limiter(y_stereo)
            y_stereo = self._loudness_normalization(y_stereo, sr)

            # 7. float32로 변환 및 저장
            y_stereo = y_stereo.astype(np.float32)
            sf.write(output_path, y_stereo.T, sr, subtype='PCM_16')

            return {
                "status": "completed",
                "output_path": output_path,
                "sample_rate": sr,
                "target_loudness": self.loudness_target
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "output_path": output_path
            }

    def _soft_clip(self, y: np.ndarray, threshold: float = 0.95) -> np.ndarray:
        """소프트 클리핑으로 클립핑 방지"""
        clipped = np.where(
            np.abs(y) > threshold,
            threshold * np.tanh(y / threshold),
            y
        )
        return clipped

    def _multiband_eq(self, y: np.ndarray, sr: int) -> np.ndarray:
        """4밴드 멀티밴드 EQ"""
        # 저역: 100Hz (감성을 위해 살짝 부스트)
        y = self._apply_peq(y, sr, freq=100, gain=2, Q=0.7)
        # 저중역: 500Hz (웜한 느낌)
        y = self._apply_peq(y, sr, freq=500, gain=1.5, Q=1)
        # 중역: 2kHz (보컬 명확성)
        y = self._apply_peq(y, sr, freq=2000, gain=2, Q=1.2)
        # 고역: 8kHz (에어감)
        y = self._apply_peq(y, sr, freq=8000, gain=1, Q=1)

        return y

    def _apply_peq(self, y: np.ndarray, sr: int, freq: float, gain: float, Q: float) -> np.ndarray:
        """매개변수 등화 필터 적용"""
        A = 10 ** (gain / 40)
        w0 = 2 * np.pi * freq / sr

        sin_w0 = np.sin(w0)
        cos_w0 = np.cos(w0)
        alpha = sin_w0 / (2 * Q)

        b0 = A * (A + 1 - (A - 1) * np.cos(w0) + 2 * np.sqrt(A) * alpha)
        b1 = 2 * A * (A - 1 - (A + 1) * np.cos(w0))
        b2 = A * (A + 1 - (A - 1) * np.cos(w0) - 2 * np.sqrt(A) * alpha)
        a0 = A + 1 + (A - 1) * np.cos(w0) + 2 * np.sqrt(A) * alpha
        a1 = -2 * (A - 1 + (A + 1) * np.cos(w0))
        a2 = A + 1 + (A - 1) * np.cos(w0) - 2 * np.sqrt(A) * alpha

        b = np.array([b0, b1, b2]) / a0
        a = np.array([1, a1 / a0, a2 / a0])

        y = signal.filtfilt(b, a, y)
        return y

    def _compression(self, y: np.ndarray, threshold: float = -20, ratio: float = 4, attack_ms: float = 10, release_ms: float = 100) -> np.ndarray:
        """동적 범위 압축"""
        sr = self.sr
        attack_samples = int(attack_ms * sr / 1000)
        release_samples = int(release_ms * sr / 1000)

        # 절대값으로 변환
        y_abs = np.abs(y)

        # 스무싱된 包络線 추출
        envelope = self._smooth_envelope(y_abs, attack_samples, release_samples)

        # 압축 곡선 적용
        gain_reduction = np.ones_like(envelope)
        above_threshold = envelope > 10 ** (threshold / 20)

        gain_reduction[above_threshold] = 10 ** (threshold / 20 + (envelope[above_threshold] - 10 ** (threshold / 20)) / ratio) / envelope[above_threshold]

        return y * gain_reduction

    def _smooth_envelope(self, signal_abs: np.ndarray, attack: int, release: int) -> np.ndarray:
        """엔벨로프 스무싱"""
        envelope = np.zeros_like(signal_abs)
        envelope[0] = signal_abs[0]

        for i in range(1, len(signal_abs)):
            if signal_abs[i] > envelope[i - 1]:
                coeff = 1 / attack
            else:
                coeff = 1 / release
            envelope[i] = coeff * signal_abs[i] + (1 - coeff) * envelope[i - 1]

        return envelope

    def _stereo_enhancement(self, y: np.ndarray) -> np.ndarray:
        """모노 신호를 스테레오로 확장 + 공간감 추가"""
        # 모노 신호를 스테레오로 변환
        y_stereo = np.stack([y, y])

        # 오른쪽 채널에 약간의 딜레이 추가 (공간감)
        delay_samples = int(0.02 * self.sr)  # 20ms
        right_delayed = np.concatenate([np.zeros(delay_samples), y[:-delay_samples]])

        y_stereo[1] = right_delayed

        # 스테레오 이미지 강화 (M/S 처리)
        mid = (y_stereo[0] + y_stereo[1]) / 2
        side = (y_stereo[0] - y_stereo[1]) / 2
        side *= 1.2  # 사이드 채널 강화

        y_stereo[0] = mid + side
        y_stereo[1] = mid - side

        return y_stereo

    def _limiter(self, y_stereo: np.ndarray, threshold: float = -1.0) -> np.ndarray:
        """제한기 (클리핑 방지)"""
        threshold_linear = 10 ** (threshold / 20)

        for i in range(y_stereo.shape[0]):
            max_val = np.max(np.abs(y_stereo[i]))
            if max_val > threshold_linear:
                y_stereo[i] *= threshold_linear / max_val

        return y_stereo

    def _loudness_normalization(self, y_stereo: np.ndarray, sr: int) -> np.ndarray:
        """간단한 RMS 정규화"""
        rms = np.sqrt(np.mean(y_stereo ** 2))
        if rms > 0:
            y_stereo *= 0.1 / rms
        return y_stereo
