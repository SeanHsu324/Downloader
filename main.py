import os
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # 避免繁中 Windows 主控台 (cp950) 印 emoji 時崩潰
import time
import threading

import cv2
import numpy as np
import torch

# 導入你提供的環境定義檔案
from big_two_model import BigTwoA2C
from agents import ModelAgent
from action_space import get_action_mask_np, INDEX_TO_ACTION_VECTOR
from big_two_core import evaluate_hand_np, compare_hands_np
from robot_arm import RobotArm, HOME
from config import (
    AI_MODEL_PATH, COM_PORT, HAND_CAMERA_INDEX, PLAY_CAMERA_INDEX,
    NUM_SLOTS, HAND_ROI, PLAY_ROI, PICK_NAME, DROP_NAME,
)
from vision import (
    Camera, GeminiCardReader, scan_hand, crop, draw_roi, put_text,
    get_card_id, id_to_card_name, names_str,
)

# =====================================================
# 1. 配置 (共用設定在 config.py：COM 埠、鏡頭編號、手牌分排、辨識區域)
# =====================================================
# --- 全自動：出牌區變化偵測 (決定何時才呼叫 Gemini) ---
MOTION_THRESH = 4.0        # 相鄰兩幀平均差異 > 此值 = 有東西在動 (手伸進來)
CHANGE_THRESH = 10.0       # 穩定後與上次基準差異 > 此值 = 桌面真的變了 -> 呼叫 Gemini
STABLE_SEC = 1.0           # 畫面需靜止多久才判定放好牌了
PASS_TIMEOUT_SEC = 15.0    # 對手回合出牌區這麼久沒變化 -> 視為 Pass (也可按 Space 手動 Pass)
ARM_SETTLE_SEC = 1.0       # 手臂動作結束後等一下再重設基準畫面

# 每打出一張牌要依序播放的動作，每張牌丟完都回初始點
# 例: 第 5 格 -> pick_05 -> drop -> home
CARD_ACTION_SEQUENCE = [PICK_NAME, DROP_NAME, HOME]

# 訓練環境 (big_two_env.py) 中「對手剩餘牌數」是原始張數，沒有除以 13
# 若你的 big_two_best.pth 是用除以 13 的版本訓練，改成 True
NORMALIZE_OPP_COUNTS = False

WINDOW = "BigTwo AI Live Control"
HAND_WINDOW = "HAND CAM"


def ids_to_vec(ids):
    v = np.zeros(52, dtype=np.int8)
    for c in ids: v[c-1] = 1
    return v


# =====================================================
# 2. 出牌區變化偵測 (決定什麼時候才叫 Gemini)
# =====================================================
class PlayZoneWatcher:
    def __init__(self):
        self.baseline = None
        self.prev = None
        self.stable_since = None
        self.last_motion_time = time.time()

    @staticmethod
    def _small(frame):
        g = cv2.cvtColor(crop(frame, PLAY_ROI), cv2.COLOR_BGR2GRAY)
        g = cv2.resize(g, (160, 90))
        return cv2.GaussianBlur(g, (5, 5), 0).astype(np.float32)

    def rebaseline(self, frame):
        self.baseline = self._small(frame)
        self.prev = self.baseline
        self.stable_since = None
        self.last_motion_time = time.time()

    def update(self, frame):
        """回傳 True 代表：出牌區有變化且已靜止，值得呼叫 Gemini"""
        small = self._small(frame)
        if self.baseline is None:
            self.rebaseline(frame)
            return False
        motion = float(np.mean(np.abs(small - self.prev)))
        self.prev = small
        now = time.time()
        if motion > MOTION_THRESH:
            self.stable_since = None
            self.last_motion_time = now
            return False
        if self.stable_since is None:
            self.stable_since = now
        if now - self.stable_since < STABLE_SEC:
            return False
        if float(np.mean(np.abs(small - self.baseline))) > CHANGE_THRESH:
            self.baseline = small   # 不論辨識結果如何，同一個畫面只叫一次 Gemini
            return True
        return False

    def idle_seconds(self):
        return time.time() - self.last_motion_time


# =====================================================
# 3. 遊戲狀態
# =====================================================
class BigTwoGame:
    def __init__(self, agent):
        self.agent = agent
        self.reset()

    def reset(self):
        # 夾取位置對應: slot(1~13) -> card_id；牌被夾走後該格設為 None
        self.slots = {i: None for i in range(1, NUM_SLOTS + 1)}
        self.last_played_cards = set()
        self.played_history = set()   # 整局已出現在桌上的牌 (用來從出牌區找出「新」的牌)
        self.others_count = [13, 13, 13]
        self.current_turn_player = 0  # 0: P1(自己), 1: P2, 2: P3, 3: P4
        self.last_action_player = 0
        self.pass_count = 0
        self.is_new_round = True
        self.game_started = False
        self.game_over = False
        self.turn_started_at = time.time()

    # --- 查詢 ---
    @property
    def hand_locked(self):
        return any(c is not None for c in self.slots.values())

    def hand_cards(self):
        return {c for c in self.slots.values() if c is not None}

    def slot_of(self, card_id):
        for s, c in self.slots.items():
            if c == card_id:
                return s
        return None

    # --- 狀態轉移 ---
    def _next_turn(self, player):
        self.current_turn_player = player
        self.turn_started_at = time.time()

    def lock_hand(self, ids, first_player=None):
        self.slots = {i + 1: cid for i, cid in enumerate(ids)}
        if 1 in ids:
            self._next_turn(0)
        elif first_player is not None:
            self._next_turn(first_player)

    def _register_pass(self, who):
        self.pass_count += 1
        print(f"[系統] P{who+1} Pass，累計 Pass: {self.pass_count}")
        if self.pass_count >= 3:
            self.is_new_round = True
            self.last_played_cards.clear()
            self.pass_count = 0
            self._next_turn(self.last_action_player)
            print(f"[系統] 三人 Pass，新回合。輪到 P{self.current_turn_player+1}")
        else:
            self._next_turn((who + 1) % 4)

    def opponent_pass(self):
        self._register_pass(self.current_turn_player)

    def is_legal_play(self, ids):
        vec = ids_to_vec(ids)
        hand_type, _ = evaluate_hand_np(vec)
        if hand_type == 0:
            return False
        if not self.last_played_cards:
            return True
        return compare_hands_np(vec, ids_to_vec(self.last_played_cards)) == 1

    def opponent_play(self, ids):
        p = self.current_turn_player
        self.others_count[p - 1] -= len(ids)
        self.last_played_cards = set(ids)
        self.played_history |= set(ids)
        self.is_new_round = False
        self.game_started = True
        self.pass_count = 0
        self.last_action_player = p
        print(f"[系統] P{p+1} 打出 {names_str(ids)}，剩 {self.others_count[p-1]} 張")
        if self.others_count[p - 1] <= 0:
            self.game_over = True
            print(f"[系統] P{p+1} 出完牌，遊戲結束")
            return
        self._next_turn((p + 1) % 4)

    def decide_my_move(self):
        """AI 決策，回傳要出的 card_id 集合 (空集合 = Pass)"""
        hand = self.hand_cards()
        if self.is_new_round and self.last_action_player == 0:
            self.last_played_cards.clear()

        obs = np.zeros(113, dtype=np.float32)
        for c in hand: obs[c-1] = 1.0
        for c in self.last_played_cards: obs[52+c-1] = 1.0
        counts = np.array(self.others_count, dtype=np.float32)
        obs[104:107] = counts / 13.0 if NORMALIZE_OPP_COUNTS else counts
        obs[107 + self.last_action_player] = 1.0
        obs[111] = float(self.pass_count)
        obs[112] = float(self.is_new_round)

        hand_vec = ids_to_vec(hand)
        # 只有整局第一手 (桌面空且手上有梅花3) 才強制出梅花3
        is_start = (not self.game_started) and not self.last_played_cards and hand_vec[0] == 1
        mask, _ = get_action_mask_np(hand_vec, ids_to_vec(self.last_played_cards), is_start_of_game=is_start)
        action_idx = self.agent.choose_action(obs, mask)
        vec = INDEX_TO_ACTION_VECTOR[action_idx]
        return {i + 1 for i, v in enumerate(vec) if v == 1}

    def apply_my_move(self, ids):
        """更新狀態並回傳要夾取的格子 (由左到右)"""
        if not ids:
            self._register_pass(0)
            return []
        card_slots = sorted(self.slot_of(c) for c in ids)
        for s in card_slots:
            self.slots[s] = None
        self.last_played_cards = set(ids)
        self.played_history |= set(ids)
        self.is_new_round = False
        self.game_started = True
        self.pass_count = 0
        self.last_action_player = 0
        if not self.hand_cards():
            self.game_over = True
            print("🎉 手牌出完，你贏了！")
        else:
            self._next_turn(1)
        return card_slots


# =====================================================
# 4. 主程序
# =====================================================
def main():
    device = torch.device("cpu")
    brain = BigTwoA2C()
    brain.load_state_dict(torch.load(AI_MODEL_PATH, map_location=device))
    agent = ModelAgent(brain, device, name="LiveAI")

    reader = GeminiCardReader()
    robot = RobotArm(COM_PORT)
    hand_cam = Camera(HAND_CAMERA_INDEX, "HAND CAM")
    play_cam = Camera(PLAY_CAMERA_INDEX, "PLAY CAM")
    watcher = PlayZoneWatcher()
    game = BigTwoGame(agent)

    auto_mode = False
    pending_hand = None           # Gemini 辨識出、尚未確認的手牌 (手動模式用)
    temp_buffer = set()           # 手動模式: P 鍵辨識到的對手出牌
    ai_suggestion = "Ready"
    need_rebaseline = False       # 手臂動作完後要重設出牌區基準畫面
    scan = {'running': False, 'result': None, 'then_auto': False}

    def show_busy(frame, msg):
        img = frame.copy()
        put_text(img, msg, 40, 2.0, (0, 0, 255), 3)
        cv2.imshow(WINDOW, img)
        cv2.waitKey(1)

    def start_scan(then_auto):
        """背景執行：手臂依序到各排拍照點 -> 手牌鏡頭拍照 -> Gemini 辨識 -> 回初始點"""
        def worker():
            try:
                result = scan_hand(robot, hand_cam, reader)
            except Exception as e:
                print(f"[Gemini] 呼叫失敗: {e}")
                result = (None, False)
                if robot.has_action(HOME) and not robot.abort.is_set():
                    robot.run_sequence([HOME], return_home=False)
                    robot.wait()
            scan['result'] = result
            scan['running'] = False

        scan.update(running=True, result=None, then_auto=then_auto)
        print("[系統] 📷 開始拍照辨識手牌...")
        threading.Thread(target=worker, daemon=True).start()

    def lock_hand(names):
        ids = [get_card_id(n) for n in names]
        first = None
        if 1 not in ids:
            ans = input("你沒有梅花3，是誰有梅花3? (輸入 2/3/4): ").strip()
            first = int(ans) - 1 if ans in ('2', '3', '4') else 1
        game.lock_hand(ids, first)
        print("[系統] 手牌已鎖定:")
        for s, c in game.slots.items():
            print(f"   第 {s:2d} 格 -> {id_to_card_name(c)}")
        print(f"[系統] 由 P{game.current_turn_player+1} 先出")

    def enable_auto():
        nonlocal auto_mode, need_rebaseline
        missing = robot.missing_actions(
            [a.format(slot=s) for s in range(1, NUM_SLOTS + 1) for a in CARD_ACTION_SEQUENCE])
        if missing:
            print(f"[警告] 缺少動作檔 {missing}，請先用 record.py 錄製")
            return
        if not robot.clamps_closed and not robot.close_clamps():
            print("[警告] 排夾無法關閉，全自動未啟動")
            return
        # 先回初始點，到位後才開始偵測出牌區
        robot.run_sequence([HOME], return_home=False)
        need_rebaseline = True
        auto_mode = True
        print("[系統] ✅ 全自動模式啟動 (按 A 關閉、S 緊急停止、Space 可手動判對手 Pass)")

    def play_my_turn():
        """AI 決策 + 叫手臂出牌"""
        nonlocal ai_suggestion, auto_mode
        ids = game.decide_my_move()
        if not ids:
            ai_suggestion = "Pass"
            print("> AI: Pass")
            game.apply_my_move(ids)
            return

        ai_suggestion = names_str(ids)
        slots_to_pick = game.apply_my_move(ids)
        print(f"> AI 出牌: {ai_suggestion}  (格子: {slots_to_pick})")

        seq = [a.format(slot=s) for s in slots_to_pick for a in CARD_ACTION_SEQUENCE]

        def on_done(ok):
            nonlocal need_rebaseline, auto_mode
            need_rebaseline = True
            if ok:
                print("[手臂] ✅ 出牌動作完成")
            else:
                auto_mode = False
                print("[手臂] ⚠️ 動作中斷，自動模式已關閉，請手動確認牌桌")

        if not robot.run_sequence(seq, on_done=on_done):
            auto_mode = False
            ai_suggestion += " (ARM FAILED - 請手動出牌)"
            print("[系統] 手臂無法執行，自動模式已關閉")

    def check_play_zone(frame):
        """出牌區有變化時呼叫 Gemini，找出對手新打出的牌"""
        show_busy(frame, "Gemini: reading play area...")
        try:
            names = reader.read_played(frame)
        except Exception as e:
            print(f"[Gemini] 呼叫失敗: {e}")
            return
        seen = {get_card_id(n) for n in names} - {None}
        new_ids = seen - game.played_history - game.hand_cards()
        print(f"[Gemini] 出牌區: {names_str(seen)} -> 新的牌: {names_str(new_ids) or '(無)'}")
        if not new_ids:
            return
        if not (1 <= len(new_ids) <= 5) or not game.is_legal_play(new_ids):
            print(f"[警告] {names_str(new_ids)} 不是合法出牌，可能辨識錯誤；"
                  f"請整理牌後再放一次，或按 P + Enter 手動輸入")
            return
        game.opponent_play(new_ids)

    print("--- 大老二 AI + 機器手臂 ---")
    print("[A] 全自動模式 開/關 (拍照辨識手牌、自動偵測對手出牌、輪到你時手臂自動出牌)")
    print("手動: [H]拍照辨識手牌 [Y]確認 [E]修改格子 [P]辨識對手出牌 [Enter]提交/AI出牌 [Space]對手Pass")
    print("[O]排夾 開/關  [C]清空緩衝 [R]重設(排夾打開) [S]緊急停止 [G]解除停止(回到跟隨示範臂) [Q]離開")

    blank = np.zeros((720, 1280, 3), dtype=np.uint8)
    while True:
        frame = play_cam.read()
        if frame is None:
            frame = blank.copy()
            put_text(frame, "PLAY CAM: no image", 400, 3.0, (0, 0, 255), 3)

        # --- 手牌辨識結果 (背景執行緒完成後) ---
        if scan['result'] is not None:
            names, ok = scan['result']
            scan['result'] = None
            if names is not None:
                if ok and scan['then_auto']:
                    lock_hand(names)
                    pending_hand = None
                    enable_auto()
                else:
                    pending_hand = names
                    print("[系統] 確認無誤請按 Y" if ok else "[系統] 請按 E 修正後按 Y，或再按 H 重拍")

        # --- 手臂動作完成後重設基準 (避免手臂入鏡被誤判) ---
        if need_rebaseline and not robot.busy and time.time() - robot.finished_at > ARM_SETTLE_SEC:
            watcher.rebaseline(frame)
            game.turn_started_at = time.time()
            need_rebaseline = False

        # --- 全自動流程 ---
        if auto_mode and not robot.busy and not need_rebaseline and not game.game_over:
            if game.current_turn_player == 0:
                play_my_turn()
            elif watcher.update(frame):
                check_play_zone(frame)
            elif (time.time() - game.turn_started_at > PASS_TIMEOUT_SEC
                  and watcher.idle_seconds() > PASS_TIMEOUT_SEC):
                print(f"[系統] P{game.current_turn_player+1} {PASS_TIMEOUT_SEC:.0f} 秒沒出牌，視為 Pass")
                game.opponent_pass()
            if game.game_over:
                auto_mode = False

        # --- UI：出牌區主畫面 ---
        view = frame.copy()
        draw_roi(view, PLAY_ROI, (255, 200, 0))
        slot_str = " ".join(f"{s}:{id_to_card_name(c) if c else '--'}" for s, c in game.slots.items())
        mode = 'SCANNING HAND' if scan['running'] else ('AUTO' if auto_mode else 'MANUAL')
        y = 30
        clamp = 'CLOSED' if robot.clamps_closed else 'OPEN'
        put_text(view, f"MODE: {mode} | ARM: {robot.status} | CLAMP: {clamp}", y, 1.2, (255, 0, 255), 2); y += 30
        put_text(view, f"SLOTS {slot_str}", y, 1.0, (0, 255, 0), 1); y += 30
        if pending_hand:
            pend = " ".join(f"{i+1}:{n}" for i, n in enumerate(pending_hand))
            put_text(view, f"GEMINI(Y=OK) {pend}", y, 1.0, (0, 255, 255), 1); y += 30
        put_text(view, f"LAST PLAY (P{game.last_action_player+1}): {names_str(game.last_played_cards)}", y, 1.2, (255, 200, 0), 2); y += 30
        if temp_buffer:
            put_text(view, f"BUFFER: {names_str(temp_buffer)}", y, 1.0, (200, 200, 200), 1); y += 30
        turn_info = f"TURN: P{game.current_turn_player+1} | PASS: {game.pass_count} | OPP: {game.others_count}"
        if auto_mode and game.current_turn_player != 0:
            left = PASS_TIMEOUT_SEC - min(time.time() - game.turn_started_at, watcher.idle_seconds())
            turn_info += f" | auto-pass in {max(0, left):.0f}s"
        put_text(view, turn_info, y, 1.0, (255, 255, 255), 1); y += 35
        put_text(view, f"AI: {ai_suggestion}", y, 1.5, (0, 0, 255), 2)
        cv2.imshow(WINDOW, view)

        # --- UI：手牌鏡頭小視窗 ---
        hand_frame = hand_cam.read()
        if hand_frame is not None:
            draw_roi(hand_frame, HAND_ROI, (0, 255, 0))
            h, w = hand_frame.shape[:2]
            cv2.imshow(HAND_WINDOW, cv2.resize(hand_frame, (480, int(h * 480 / w))))

        key = cv2.waitKey(1) & 0xFF

        if key == ord('q'):
            break

        elif key == ord('s'):  # 緊急停止 (手臂播放中也有效)
            robot.emergency_stop()
            auto_mode = False

        elif key == ord('g'):
            robot.resume_live()
            print("[系統] 已解除緊急停止，手臂回到跟隨示範臂模式")

        elif robot.busy or scan['running']:
            continue  # 手臂動作 / 拍照辨識中只接受 S / Q

        elif key == ord('a'):  # 全自動開關
            if auto_mode:
                auto_mode = False
                print("[系統] 全自動模式關閉")
            elif not game.hand_locked:
                start_scan(then_auto=True)   # 辨識完整就自動鎖定並開始
            else:
                enable_auto()

        elif key == ord('h'):
            start_scan(then_auto=False)

        elif key == ord('e'):  # 手動修改某一格 (會暫停畫面等待輸入)
            if pending_hand is None:
                pending_hand = [id_to_card_name(c) if c else '??' for c in game.slots.values()]
            txt = input("輸入要修改的格子與牌名，例如 5=SA (可用空白分隔多筆): ").strip()
            for item in txt.split():
                try:
                    s, n = item.split('=')
                    s = int(s)
                    if 1 <= s <= NUM_SLOTS and get_card_id(n):
                        pending_hand[s-1] = n.upper().replace('10', 'T')
                    else:
                        print(f"[警告] 無效輸入: {item}")
                except ValueError:
                    print(f"[警告] 格式錯誤: {item}")
            print(f"[系統] 待確認手牌: {pending_hand}，按 Y 確認")

        elif key == ord('y'):
            if pending_hand is None:
                print("[警告] 沒有待確認的手牌，請先按 H")
                continue
            ids = [get_card_id(n) for n in pending_hand]
            if None in ids or len(set(ids)) != NUM_SLOTS:
                print(f"[警告] 手牌不完整或有重複: {pending_hand}，請按 E 修正")
                continue
            lock_hand(pending_hand)
            pending_hand = None

        elif key == ord('p'):  # 手動: Gemini 辨識對手出的牌
            show_busy(frame, "Gemini: reading played cards...")
            try:
                names = reader.read_played(frame)
            except Exception as e:
                print(f"[Gemini] 呼叫失敗: {e}")
                continue
            temp_buffer = {get_card_id(n) for n in names} - {None} - game.played_history
            print(f"[Gemini] 對手出牌: {names_str(temp_buffer)} (按 Enter 提交，C 清空)")

        elif key == 32:  # Space: 對手 Pass
            if game.current_turn_player == 0:
                print("[警告] 現在是你的回合")
                continue
            game.opponent_pass()
            temp_buffer.clear()
            if auto_mode:
                watcher.rebaseline(frame)

        elif key == ord('o'):  # 手動開關排夾
            if auto_mode:
                print("[警告] 全自動中不能開排夾，請先按 A 關閉全自動")
            elif robot.clamps_closed:
                robot.open_clamps()
            else:
                robot.close_clamps()

        elif key == ord('c'):
            temp_buffer.clear()
            print("[系統] 緩衝區已清空")

        elif key == ord('r'):
            game.reset()
            auto_mode = False
            pending_hand = None
            temp_buffer.clear()
            ai_suggestion = "Ready"
            robot.open_clamps()   # 新局：打開排夾讓你插牌
            print("[系統] 遊戲狀態已完全重置")

        elif key == 13:  # Enter (手動模式)
            if game.current_turn_player == 0:
                if not game.hand_locked:
                    print("[警告] 尚未鎖定手牌，請先按 H 再按 Y")
                    continue
                play_my_turn()
            elif temp_buffer:
                game.opponent_play(temp_buffer)
                temp_buffer = set()
            else:
                print(f"[警告] 現在是 P{game.current_turn_player+1} 的回合，請先按 P 辨識出牌，再按 Enter。")

    hand_cam.release()
    play_cam.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
