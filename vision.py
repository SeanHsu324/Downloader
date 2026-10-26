"""
鏡頭 + Gemini 辨識 (main.py / record.py 共用)
"""
import os
import sys
import json
import time
import threading

import cv2
import numpy as np

from config import (
    CAMERA_WIDTH, CAMERA_HEIGHT, GEMINI_MODEL, HAND_ROI, PLAY_ROI,
    HAND_ZONES, NUM_SLOTS, PHOTO_SETTLE_SEC, HAND_REVERSED, SNAPSHOT_DIR,
)
from robot_arm import HOME

# =====================================================
# 牌名 <-> 編號
# =====================================================
# 0-12: 梅花(C), 13-25: 方塊(D), 26-38: 紅心(H), 39-51: 黑桃(S)
SUIT_ORDER = ['C', 'D', 'H', 'S']
RANK_ORDER = ['3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A', '2']
CARD_NAMES = [s + r for s in SUIT_ORDER for r in RANK_ORDER]  # 規定名稱，例: C3, DT, SA, H2


def get_card_id(name):
    """牌名 -> 1~52，無法辨識回傳 None"""
    if not isinstance(name, str):
        return None
    name = name.strip().upper().replace('10', 'T')
    if len(name) != 2:
        return None
    s, r = name[0], name[1]
    if s not in SUIT_ORDER or r not in RANK_ORDER:
        return None
    return SUIT_ORDER.index(s) * 13 + RANK_ORDER.index(r) + 1


def id_to_card_name(card_id):
    if not (1 <= card_id <= 52): return "??"
    return f"{SUIT_ORDER[(card_id-1)//13]}{RANK_ORDER[(card_id-1)%13]}"


def names_str(ids):
    return " ".join(id_to_card_name(c) for c in sorted(ids))


def crop(frame, roi):
    if roi is None:
        return frame
    h, w = frame.shape[:2]
    x, y, rw, rh = roi
    return frame[int(y*h):int((y+rh)*h), int(x*w):int((x+rw)*w)]


def draw_roi(img, roi, color):
    if roi is None:
        return
    h, w = img.shape[:2]
    x, y, rw, rh = roi
    cv2.rectangle(img, (int(x*w), int(y*h)), (int((x+rw)*w), int((y+rh)*h)), color, 2)


def put_text(img, text, y, scale, color, thick, x=20):
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_PLAIN, scale, color, thick)


# =====================================================
# 鏡頭 (背景持續讀取，永遠拿到最新畫面)
# =====================================================
class Camera:
    def __init__(self, index, name):
        self.index = index
        self.name = name
        backend = cv2.CAP_DSHOW if sys.platform == 'win32' else cv2.CAP_ANY
        self.cap = cv2.VideoCapture(index, backend)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
        self.ok = self.cap.isOpened()
        self._frame = None
        self._frame_time = 0.0
        self._lock = threading.Lock()
        self._running = self.ok
        if self.ok:
            threading.Thread(target=self._loop, daemon=True).start()
            print(f"[鏡頭] {name} (編號 {index}) 已開啟")
        else:
            print(f"[鏡頭] ❌ {name} (編號 {index}) 開不起來，請用 record.py 的 cams 指令確認編號")

    def _loop(self):
        while self._running:
            ret, frame = self.cap.read()
            if ret:
                with self._lock:
                    self._frame = frame
                    self._frame_time = time.time()
            else:
                time.sleep(0.01)

    def read(self):
        """最新畫面 (可能為 None)"""
        with self._lock:
            return None if self._frame is None else self._frame.copy()

    def fresh(self, timeout=2.0):
        """等一張「呼叫之後才拍到」的畫面 (手臂剛停下時用，避免拿到移動中的舊畫面)"""
        t0 = time.time()
        while time.time() - t0 < timeout:
            with self._lock:
                if self._frame is not None and self._frame_time > t0 + 0.05:
                    return self._frame.copy()
            time.sleep(0.01)
        return self.read()

    def release(self):
        self._running = False
        time.sleep(0.05)
        self.cap.release()


def probe_cameras(max_index=6, skip=()):
    """列出可以開啟的鏡頭編號"""
    found = []
    backend = cv2.CAP_DSHOW if sys.platform == 'win32' else cv2.CAP_ANY
    for i in range(max_index):
        if i in skip:
            found.append((i, '使用中'))
            continue
        cap = cv2.VideoCapture(i, backend)
        if cap.isOpened():
            ret, frame = cap.read()
            found.append((i, f"{frame.shape[1]}x{frame.shape[0]}" if ret else '開得起來但讀不到畫面'))
        cap.release()
    return found


# =====================================================
# Gemini 辨識 (只在需要時呼叫)
# =====================================================
RULES = (
    "Card naming rule: suit letter + rank letter, exactly 2 characters.\n"
    "Suits: C=Clubs, D=Diamonds, H=Hearts, S=Spades.\n"
    "Ranks: 3 4 5 6 7 8 9 T(=10) J Q K A 2.\n"
    "Examples: 'C3' = 3 of clubs, 'DT' = 10 of diamonds, 'SA' = ace of spades, 'H2' = 2 of hearts.\n"
)

HAND_PROMPT = (
    "This image shows exactly {n} playing cards standing upright, face visible, in a single row "
    "inside a card holder rack. Cards may overlap slightly; read the rank/suit index in each card's corner.\n"
    + RULES +
    "List every card strictly from LEFT to RIGHT as they appear in the image. "
    "The array must have exactly {n} entries, one per card position, no duplicates. "
    "Return only the JSON array."
)

PLAY_PROMPT = (
    "This image shows the play area of a card game table.\n"
    + RULES +
    "List every distinct face-up card whose rank and suit you can identify, from left to right. "
    "Return only the JSON array. If there are no cards, return []."
)


class GeminiCardReader:
    def __init__(self, model=GEMINI_MODEL):
        from google import genai
        from google.genai import types
        self.types = types
        self.client = genai.Client()  # 自動讀取 GEMINI_API_KEY
        self.model = model
        self.schema = types.Schema(
            type=types.Type.ARRAY,
            items=types.Schema(type=types.Type.STRING, enum=CARD_NAMES),
        )

    def _ask(self, image, prompt):
        ok, jpg = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 90])
        if not ok:
            raise RuntimeError("影像編碼失敗")
        types = self.types
        resp = self.client.models.generate_content(
            model=self.model,
            contents=[types.Part.from_bytes(data=jpg.tobytes(), mime_type='image/jpeg'), prompt],
            config=types.GenerateContentConfig(
                response_mime_type='application/json',
                response_schema=self.schema,
                temperature=0,
            ),
        )
        return [n.strip().upper() for n in json.loads(resp.text)]

    def read_hand(self, frame, n):
        """回傳該排由左到右的牌名陣列 (長度應為 n)"""
        return self._ask(crop(frame, HAND_ROI), HAND_PROMPT.format(n=n))

    def read_played(self, frame):
        """回傳出牌區看得到的所有牌名"""
        return self._ask(crop(frame, PLAY_ROI), PLAY_PROMPT)


def save_snapshot(frame, tag):
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    path = os.path.join(SNAPSHOT_DIR, f"{tag}_{time.strftime('%Y%m%d_%H%M%S')}.jpg")
    cv2.imwrite(path, frame)
    return path


def capture_zone(robot, hand_cam, zone):
    """手臂移到該排拍照點 -> 等穩定 -> 拍照。失敗回傳 None"""
    pose = zone['pose']
    if not robot.has_action(pose):
        print(f"[手牌] ❌ 缺少拍照點 {pose}，請用 record.py 設定")
        return None
    robot.run_sequence([pose], return_home=False)
    robot.wait()
    if robot.abort.is_set():
        return None
    time.sleep(PHOTO_SETTLE_SEC)
    frame = hand_cam.fresh()
    if frame is not None:
        save_snapshot(frame, pose)
    return frame


def read_zone(reader, frame, zone):
    names = reader.read_hand(frame, zone['count'])
    print(f"[Gemini] {zone['label']} 由左到右: {names}")
    names = (names + ['??'] * zone['count'])[:zone['count']]
    return names[::-1] if HAND_REVERSED else names


def scan_hand(robot, hand_cam, reader):
    """
    依序到每一排的拍照點拍照並辨識，回初始點後關閉排夾。
    回傳 (13 個牌名，依格子 1~13 排列, 是否完整可用)；手臂中斷回傳 (None, False)
    """
    all_names = []
    for zone in HAND_ZONES:
        frame = capture_zone(robot, hand_cam, zone)
        if frame is None:
            return None, False
        all_names += read_zone(reader, frame, zone)
    if robot.has_action(HOME):
        robot.run_sequence([HOME], return_home=False)
        robot.wait()
    if robot.abort.is_set():
        return None, False
    robot.close_clamps()   # 拍完兩排、回到初始點 -> 夾住手牌

    ids = [get_card_id(n) for n in all_names]
    valid = None not in ids and len(set(ids)) == NUM_SLOTS
    if not valid:
        print("[警告] 手牌辨識不完整或有重複，可重新辨識，或按 E 手動修改後按 Y")
    return all_names, valid
