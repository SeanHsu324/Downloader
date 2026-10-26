"""
機器手臂共用模組 (錄製程式 record.py 與 main.py 共用)

ESP32 韌體行為：
  - 即時連動模式：從手臂跟隨示範臂，並回傳 DATA,j1..j6 (只有這個模式能錄製)
  - 播放模式：收到 P,j1..j6 後直接驅動伺服，不再跟隨示範臂 (此模式沒有限速！)
  - s = 緊急停止，r = 解除停止並回到即時連動 (手臂會移到示範臂當下的姿勢)
"""
import os
import json
import time
import threading

import numpy as np

from config import CLAMP_OPEN, CLAMP_CLOSED, CLAMP_SETTLE_SEC

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ACTIONS_DIR = os.path.join(BASE_DIR, 'actions')

BAUD_RATE = 115200
FRAME_DT = 0.02          # 50Hz，與韌體一致
MAX_STEP_DEG = 8         # 動作銜接時每幀最多變化角度 (與韌體 MAX_SPEED 相同)
HOME = 'home'            # 初始點動作檔名稱 (actions/home.json，只有一個點位)
IDLE_TOL_DEG = 1         # 錄製頭尾「沒在動」的判定容許誤差
# 與韌體 (firmware/esp32_arm) 相同的角度限制，用來預測手臂實際會停在哪
MIN_ANGLE, MAX_ANGLE, J6_MAX_ANGLE = 5, 175, 180


def clamp_angles(angles):
    return [max(MIN_ANGLE, min(J6_MAX_ANGLE if i == 5 else MAX_ANGLE, int(a))) for i, a in enumerate(angles)]


def trim_idle(frames, tol=IDLE_TOL_DEG):
    """去掉錄製開頭與結尾手臂靜止不動的點位 (按指令時的空檔)"""
    if len(frames) < 3:
        return frames
    arr = np.array(frames)

    def moved(i, j):
        return np.max(np.abs(arr[i] - arr[j])) > tol

    start = 0
    while start < len(arr) - 1 and not moved(start, 0):
        start += 1
    end = len(arr) - 1
    while end > start and not moved(end, len(arr) - 1):
        end -= 1
    # 頭尾補回原本的靜止姿勢，讓動作起點/終點完整
    return [frames[0]] + frames[start:end + 1] + [frames[-1]]


class RobotArm:
    def __init__(self, port, baud=BAUD_RATE):
        os.makedirs(ACTIONS_DIR, exist_ok=True)
        self.ser = None
        self.current_angles = None   # 最後已知 (或最後送出) 的六軸角度
        self.mode = 'live'           # live / playback / stopped
        self.abort = threading.Event()
        self.busy = False
        self.status = "Idle"
        self.finished_at = 0.0

        self.is_recording = False
        self.recorded_frames = []

        self._state = None                  # 韌體回應 ? 的 (模式, 角度)
        self.clamp_angles = list(CLAMP_OPEN)  # 排夾 J7, J8 (韌體開機預設全開)
        self._state_event = threading.Event()
        self._warned_no_state = False

        if port is None:
            print("[手臂] 模擬模式 (未連接 ESP32)")
            return
        import serial
        print(f"[手臂] 正在連接 ESP32 ({port})...")
        self.ser = serial.Serial(port, baud, timeout=1)
        time.sleep(2)  # 等待 ESP32 重啟就緒
        threading.Thread(target=self._receive_loop, daemon=True).start()
        st = self.query_state(timeout=1.0)
        if st:
            print(f"[手臂] 連線成功，韌體回應正常 (模式 {st[0]}, 角度 {st[1]})")
        else:
            print("[手臂] ⚠️ 已連線但韌體沒有回應狀態查詢，請確認已燒錄 firmware/esp32_arm")

    # ---------------- 接收 ----------------
    def _receive_loop(self):
        while True:
            try:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                if line.startswith("DATA,"):
                    parts = line.split(",")[1:]
                    if len(parts) == 6 and not self.busy:
                        angles = [int(p) for p in parts]
                        self.current_angles = angles
                        if self.is_recording:
                            self.recorded_frames.append(angles)
                elif line.startswith("STATE,"):
                    parts = line.split(",")
                    if len(parts) in (8, 10):
                        self._state = (parts[1], [int(p) for p in parts[2:8]])
                        if len(parts) == 10:
                            self.clamp_angles = [int(p) for p in parts[8:10]]
                        self._state_event.set()
                elif line.startswith("STATUS:"):
                    print(f"\n[ESP32 回報] {line}")
                elif line.startswith("ERR"):
                    print(f"\n[ESP32 錯誤] {line}")
            except Exception:
                pass

    # ---------------- 動作檔 ----------------
    @staticmethod
    def action_path(name):
        return os.path.join(ACTIONS_DIR, f"{name}.json")

    def has_action(self, name):
        return os.path.exists(self.action_path(name))

    def missing_actions(self, names):
        return [n for n in names if not self.has_action(n)]

    def load_frames(self, name):
        with open(self.action_path(name), 'r', encoding='utf-8') as f:
            return json.load(f).get('frames', [])

    def save_action(self, name, frames):
        with open(self.action_path(name), 'w', encoding='utf-8') as f:
            json.dump({"name": name, "count": len(frames), "frames": frames}, f, indent=2)

    def home_angles(self):
        return self.load_frames(HOME)[0] if self.has_action(HOME) else None

    # ---------------- 模式切換 ----------------
    def live(self):
        """回到即時連動 (從手臂會跟隨示範臂)"""
        self.abort.clear()
        if self.ser is not None:
            self.ser.write(b"r\n")
        self.mode = 'live'
        self.status = "Idle"
        time.sleep(0.2)

    def emergency_stop(self):
        self.abort.set()
        if self.ser is not None:
            self.ser.write(b"s\n")
        self.mode = 'stopped'
        self.status = "STOPPED"
        print("[手臂] ⛔ 緊急停止")

    # 舊名稱相容
    resume_live = live

    # ---------------- 錄製 ----------------
    def start_recording(self):
        if self.mode != 'live':
            # 只有即時連動模式 ESP32 才會回傳角度
            self.live()
        self.recorded_frames = []
        self.is_recording = True

    def stop_recording(self, name, trim=True):
        self.is_recording = False
        frames = trim_idle(self.recorded_frames) if trim else self.recorded_frames
        if not frames:
            print("⚠️ 沒有錄到任何點位 (ESP32 有在即時連動模式嗎？)")
            return 0
        self.save_action(name, frames)
        return len(frames)

    def save_pose(self, name):
        """把從手臂目前姿勢存成單點動作 (初始點、拍照點)"""
        if self.mode != 'live' or self.current_angles is None:
            print("⚠️ 需在即時連動模式下才能讀到目前角度，請先輸入 r")
            return None
        angles = list(self.current_angles)
        self.save_action(name, [angles])
        return angles

    def set_home(self):
        return self.save_pose(HOME)

    # ---------------- 狀態查詢 / 確認有照指令動作 ----------------
    def query_state(self, timeout=0.5):
        """問韌體目前模式與輸出角度，回傳 (模式, [j1..j6])；沒回應回傳 None"""
        if self.ser is None:
            return ('SIM', self.current_angles)
        self._state_event.clear()
        self.ser.write(b"?\n")
        if not self._state_event.wait(timeout):
            return None
        return self._state

    # ---------------- 排夾 ----------------
    @property
    def clamps_closed(self):
        return list(self.clamp_angles) == list(CLAMP_CLOSED)

    def set_clamps(self, angles):
        """設定排夾 J7, J8 角度，並跟韌體確認。回傳是否成功"""
        angles = [int(a) for a in angles]
        if self.ser is None:
            self.clamp_angles = angles
            print(f"[排夾] (模擬) J7={angles[0]} J8={angles[1]}")
            return True
        if self.mode == 'stopped':
            print("[排夾] ⛔ 緊急停止中，請先解除停止")
            return False
        self.ser.write(f"C,{angles[0]},{angles[1]}\n".encode())
        time.sleep(CLAMP_SETTLE_SEC)
        st = self.query_state()
        if st is None:
            print("[排夾] ⚠️ 韌體沒有回應，無法確認排夾狀態")
            return False
        if self.clamp_angles != angles:
            print(f"[排夾] ❌ 韌體回報 {self.clamp_angles}，預期 {angles} (韌體版本太舊？)")
            return False
        return True

    def open_clamps(self):
        ok = self.set_clamps(CLAMP_OPEN)
        if ok:
            print("[排夾] 🔓 已開啟")
        return ok

    def close_clamps(self):
        ok = self.set_clamps(CLAMP_CLOSED)
        if ok:
            print("[排夾] 🔒 已關閉")
        return ok

    def verify_position(self, expected, tol=1):
        """確認韌體輸出角度 = 最後送出的角度。True 成功 / False 不符 / None 韌體沒回應"""
        if self.ser is None:
            return True
        st = self.query_state()
        if st is None:
            return None
        mode, angles = st
        diff = max(abs(a - b) for a, b in zip(angles, clamp_angles(expected)))
        if mode != 'PLAYBACK' or diff > tol:
            print(f"[手臂] ⚠️ 韌體狀態 {mode} 角度 {angles}，預期 {clamp_angles(expected)}")
            return False
        return True

    def self_test(self, step=5):
        """
        確認 ESP32 收到指令會動作：狀態查詢 -> J1 轉 step 度再轉回 -> 緊急停止時不會動 -> 回到即時連動。
        只會讓底座 J1 小幅轉動。回傳是否全部通過。
        """
        if self.ser is None:
            print("模擬模式無法測試")
            return False
        if self.busy:
            print("手臂忙碌中")
            return False
        results = []

        def check(name, ok, info=""):
            results.append(ok)
            print(f"   {'✅' if ok else '❌'} {name} {info}")

        st = self.query_state(1.0)
        check("韌體回應狀態查詢", st is not None, st or "(沒回應，是不是舊韌體？)")
        if st is None:
            return False
        if st[0] == 'EMERGENCY_STOP':
            self.live()
            time.sleep(0.5)
            st = self.query_state(1.0)
        base = clamp_angles(st[1])

        self.busy = True
        try:
            self._send(base)                       # 進入播放模式，角度不變
            time.sleep(0.3)
            check("進入播放模式", self.verify_position(base) is True)
            moved = list(base)
            moved[0] += step if moved[0] + step <= MAX_ANGLE else -step
            self._send(moved)
            time.sleep(0.5)
            check(f"J1 轉 {step}° ({base[0]} -> {moved[0]})", self.verify_position(moved) is True)
            self._send(base)
            time.sleep(0.5)
            check("J1 轉回原位", self.verify_position(base) is True)

            self.ser.write(b"s\n")
            time.sleep(0.2)
            self._send(moved)                      # 停止中送指令，不應該動
            time.sleep(0.3)
            st = self.query_state()
            check("緊急停止時忽略動作指令",
                  st is not None and st[0] == 'EMERGENCY_STOP' and st[1][0] == base[0],
                  f"(J1={st[1][0]})" if st else "")
            self.current_angles = base
        finally:
            self.busy = False
        self.live()                                # 解除停止，回到跟隨示範臂
        time.sleep(0.3)
        st = self.query_state()
        check("解除停止回到即時連動", st is not None and st[0] == 'RUNNING')
        return all(results)

    # ---------------- 播放 ----------------
    def _send(self, angles):
        angles = [int(a) for a in angles]
        if self.ser is not None:
            self.ser.write(("P," + ",".join(map(str, angles)) + "\n").encode('utf-8'))
        self.current_angles = angles
        self.mode = 'playback'
        time.sleep(FRAME_DT)

    def _move_to(self, target):
        # 播放模式下韌體沒有限速，動作與動作之間用插值平滑銜接
        if self.current_angles is None:
            self._send(target)
            return
        start = np.array(self.current_angles, dtype=float)
        target = np.array(target, dtype=float)
        steps = int(np.ceil(np.max(np.abs(target - start)) / MAX_STEP_DEG))
        for i in range(1, steps + 1):
            if self.abort.is_set():
                return
            self._send(np.round(start + (target - start) * i / steps))

    def _play(self, name):
        frames = self.load_frames(name)
        if not frames:
            return
        self.status = f"Playing {name}"
        print(f"[手臂] ▶ {name} ({len(frames)} 點)")
        self._move_to(frames[0])
        for frame in frames:
            if self.abort.is_set():
                return
            self._send(frame)

    def run_sequence(self, names, on_done=None, return_home=True):
        """
        背景依序播放動作，結束後自動回到初始點 (return_home)。
        播放中仍可呼叫 emergency_stop()。
        """
        if self.busy:
            print("[手臂] 忙碌中，忽略新指令")
            return False
        if self.mode == 'stopped':
            print("[手臂] ⛔ 緊急停止中，請先解除停止 (r / G)")
            return False
        names = list(names)
        if return_home and self.has_action(HOME) and (not names or names[-1] != HOME):
            names.append(HOME)
        missing = self.missing_actions(names)
        if missing:
            print(f"[手臂] ❌ 缺少動作檔: {missing}")
            return False

        def worker():
            ok = True
            try:
                for name in names:
                    self._play(name)
                    if self.abort.is_set():
                        ok = False
                        break
            except Exception as e:
                ok = False
                print(f"[手臂] 播放錯誤: {e}")
            if ok and self.current_angles is not None:
                # 確認 ESP32 真的照指令輸出到最後的角度
                v = self.verify_position(self.current_angles)
                if v is False:
                    ok = False
                    print("[手臂] ❌ ESP32 沒有照指令動作，已中止")
                elif v is None and not self._warned_no_state:
                    self._warned_no_state = True
                    print("[手臂] ⚠️ 韌體沒回應狀態查詢，無法確認是否到位 (請燒錄 firmware/esp32_arm)")
            self.status = "Idle" if ok else "STOPPED"
            self.finished_at = time.time()
            self.busy = False
            if on_done:
                on_done(ok)

        self.busy = True
        self.abort.clear()
        threading.Thread(target=worker, daemon=True).start()
        return True

    def wait(self):
        while self.busy:
            time.sleep(0.05)
