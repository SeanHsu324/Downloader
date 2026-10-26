"""
ESP32 機器手臂 動作錄製 / 拍照點設定 / 辨識測試 控制台
(會同時開啟兩顆鏡頭的預覽視窗，方便對準)

需要準備的動作 (名稱要完全一樣，main.py 會用到)：
  home        : 初始點 (指令 h，存目前姿勢，只有一個點)
  photo_1, 2  : 第一排/第二排的拍照點 (指令 c 1 / c 2，看 HAND CAM 視窗對準後存)
  pick_01~13  : 從初始點 -> 手牌架第 N 格 -> 夾緊 -> 提起，停在「拿牌姿勢」
  drop        : 從「拿牌姿勢」-> 往前甩 -> 張開夾爪把牌丟到出牌區
每個動作播完都會自動回到 home。
"""
import os
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # 避免繁中 Windows 主控台 (cp950) 印 emoji 時崩潰
import time
import threading

import cv2
import numpy as np

from config import (
    COM_PORT, HAND_CAMERA_INDEX, PLAY_CAMERA_INDEX, HAND_ZONES, NUM_SLOTS,
    HAND_ROI, PLAY_ROI, PICK_NAME, DROP_NAME,
)
from robot_arm import RobotArm, HOME, ACTIONS_DIR, FRAME_DT
from vision import (
    Camera, probe_cameras, draw_roi, put_text, save_snapshot,
    capture_zone, read_zone, scan_hand,
)


def pick_name(slot):
    return PICK_NAME.format(slot=slot)


def zone_slots(zi):
    """第 zi 排 (0 起算) 對應的格子編號"""
    start = sum(z['count'] for z in HAND_ZONES[:zi]) + 1
    return list(range(start, start + HAND_ZONES[zi]['count']))


def required_actions():
    return ([HOME] + [z['pose'] for z in HAND_ZONES]
            + [pick_name(s) for s in range(1, NUM_SLOTS + 1)] + [DROP_NAME])


# =====================================================
# 鏡頭預覽 (背景執行緒，主執行緒可以照常 input())
# =====================================================
class Preview:
    def __init__(self, robot):
        self.robot = robot
        self.hand_cam = Camera(HAND_CAMERA_INDEX, "HAND CAM")
        self.play_cam = Camera(PLAY_CAMERA_INDEX, "PLAY CAM")
        self.hint = ""
        self._running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def _show(self, cam, roi, title):
        frame = cam.read()
        if frame is None:
            return
        view = frame.copy()
        h, w = view.shape[:2]
        draw_roi(view, roi, (0, 255, 0))
        cv2.line(view, (w // 2, 0), (w // 2, h), (80, 80, 80), 1)   # 中線，方便對準
        put_text(view, f"{title} | ARM: {self.robot.status} ({self.robot.mode})", 30, 1.6, (0, 0, 255), 2)
        if self.hint:
            put_text(view, self.hint, 60, 1.6, (0, 255, 255), 2)
        scale = 640 / w
        cv2.imshow(title, cv2.resize(view, (640, int(h * scale))))

    def _loop(self):
        while self._running:
            self._show(self.hand_cam, HAND_ROI, "HAND CAM")
            self._show(self.play_cam, PLAY_ROI, "PLAY CAM")
            cv2.waitKey(30)

    def close(self):
        self._running = False
        time.sleep(0.1)
        self.hand_cam.release()
        self.play_cam.release()
        cv2.destroyAllWindows()


# =====================================================
# 錄製 / 設定
# =====================================================
def show_home_distance(robot):
    home = robot.home_angles()
    if home is None or robot.current_angles is None:
        return
    diff = np.max(np.abs(np.array(robot.current_angles) - np.array(home)))
    print(f"   (示範臂目前與初始點最大差距 {diff:.0f}°{'，OK' if diff <= 5 else '，建議先擺回初始點'})")


def record_once(robot, preview, name, hint=""):
    """互動錄製一個動作：Enter 開始、Enter 結束，可試播與重錄。回傳 False 表示使用者要中止"""
    while True:
        print(f"\n🎬 [{name}] {hint}")
        preview.hint = f"REC {name}"
        robot.live()
        time.sleep(0.3)
        show_home_distance(robot)
        cmd = input("   按 Enter 開始錄製 (skip=跳過, q=結束): ").strip().lower()
        if cmd == 'q':
            return False
        if cmd == 'skip':
            return True

        robot.start_recording()
        preview.hint = f"RECORDING {name} ..."
        print("   🔴 錄製中... 擺動示範臂，完成後按 Enter")
        input()
        count = robot.stop_recording(name)
        preview.hint = ""
        if count == 0:
            continue
        print(f"   ✅ 已存 {name} ({count} 點 / 約 {count*FRAME_DT:.1f} 秒，已去除頭尾靜止段)")

        ans = input("   [Enter]下一個  [p]試播(播完回初始點)  [r]重錄: ").strip().lower()
        if ans == 'p':
            robot.run_sequence([name])
            robot.wait()
            ans = input("   [Enter]滿意，下一個  [r]重錄: ").strip().lower()
        if ans != 'r':
            return True


def set_photo_pose(robot, preview, zi):
    """跟隨示範臂，看 HAND CAM 視窗對準第 zi 排後存成拍照點。回傳 False 表示中止"""
    zone = HAND_ZONES[zi]
    slots = zone_slots(zi)
    print(f"\n📷 [{zone['pose']}] {zone['label']}：格子 {slots[0]}~{slots[-1]}，共 {zone['count']} 張")
    print("   移動示範臂，讓 HAND CAM 畫面中這一排的牌全部入鏡、牌角清楚 (綠框 = HAND_ROI)")
    preview.hint = f"AIM {zone['label']} -> Enter to save"
    robot.live()
    ans = input("   對準後按 Enter 儲存 (skip=跳過, q=結束): ").strip().lower()
    preview.hint = ""
    if ans == 'q':
        return False
    if ans == 'skip':
        return True
    angles = robot.save_pose(zone['pose'])
    if angles:
        print(f"   ✅ 已存 {zone['pose']}: {angles}")
    return True


def batch_record(robot, preview):
    if not robot.has_action(HOME):
        print("⚠️ 請先用 h 設定初始點")
        return
    print("\n====== 批次設定：拍照點 + pick_01~13 + drop ======")
    for zi in range(len(HAND_ZONES)):
        if not set_photo_pose(robot, preview, zi):
            return
    for zi, zone in enumerate(HAND_ZONES):
        print(f"\n--- {zone['label']} (由 HAND CAM 畫面左到右 = 格子 {zone_slots(zi)}) ---")
        for slot in zone_slots(zi):
            if not record_once(robot, preview, pick_name(slot),
                               f"{zone['label']} 第 {slot} 格夾牌，提起後停在「拿牌姿勢」"):
                return
    record_once(robot, preview, DROP_NAME, "從「拿牌姿勢」(夾爪保持夾緊) 開始 -> 往前甩 -> 張開夾爪丟牌")
    print("✅ 批次設定完成，可用 v all 測試整副手牌辨識")


# =====================================================
# 測試
# =====================================================
_reader = None


def get_reader():
    global _reader
    if _reader is None:
        from vision import GeminiCardReader
        _reader = GeminiCardReader()
    return _reader


def test_vision(robot, preview, arg):
    try:
        reader = get_reader()
        if arg == 'all':
            names, ok = scan_hand(robot, preview.hand_cam, reader)
            if names:
                for i, n in enumerate(names, 1):
                    print(f"   第 {i:2d} 格 -> {n}")
                print("   ✅ 完整" if ok else "   ⚠️ 有缺漏或重複")
        elif arg == 'p':
            frame = preview.play_cam.fresh()
            print(f"   出牌區: {reader.read_played(frame)}  (照片: {save_snapshot(frame, 'play')})")
        elif arg.isdigit() and 1 <= int(arg) <= len(HAND_ZONES):
            zi = int(arg) - 1
            frame = capture_zone(robot, preview.hand_cam, HAND_ZONES[zi])
            if frame is not None:
                names = read_zone(reader, frame, HAND_ZONES[zi])
                for slot, n in zip(zone_slots(zi), names):
                    print(f"   第 {slot:2d} 格 -> {n}")
            if robot.has_action(HOME):
                robot.run_sequence([HOME], return_home=False)
        else:
            print(f"⚠️ 用法: v 1~{len(HAND_ZONES)} / v all / v p")
    except Exception as e:
        print(f"[Gemini] 呼叫失敗: {e}")


def test_slot(robot, slot):
    names = [pick_name(slot), DROP_NAME]
    missing = robot.missing_actions(names)
    if missing:
        print(f"❌ 缺少動作: {missing}")
        return
    print(f"▶️ 測試出第 {slot} 格: {' -> '.join(names)} -> {HOME}")
    robot.run_sequence(names, on_done=lambda ok: print("✅ 測試完成" if ok else "⚠️ 測試中斷"))


def list_actions(robot):
    files = sorted(f for f in os.listdir(ACTIONS_DIR) if f.endswith('.json'))
    print("\n================ 已儲存的動作 ================")
    for f in files:
        name = f[:-5]
        count = len(robot.load_frames(name))
        print(f"  {name:<12} ({count} 點位 / 約 {count*FRAME_DT:.1f} 秒)")
    missing = robot.missing_actions(required_actions())
    print("----------------------------------------------")
    print("  main.py 需要的動作: " + ("全部齊全 ✅" if not missing else f"缺少 {missing}"))
    print("==============================================\n")


HELP = f"""
=======================================================
   ESP32 機器手臂 錄製 / 設定控制台   (鏡頭預覽視窗會一直開著)
=======================================================
  設定
  [h]            : 把目前姿勢設為初始點 (home)
  [c 排號]       : 把目前姿勢設為該排拍照點 (例: c 1)，看 HAND CAM 對準
  [b]            : 批次設定 拍照點 -> pick_01~13 -> drop (建議用這個)
  [1 名稱]       : 錄製單一動作 (例: 1 pick_05、1 drop)
  [2 名稱]       : 刪除動作
  [3]            : 列出動作 (並檢查 main.py 需要的是否齊全)
  移動 / 測試
  [home]         : 回到初始點
  [go 排號]      : 移到該排拍照點並停住 (例: go 2)
  [4 名稱]       : 播放動作 (播完自動回初始點)
  [t 格號]       : 測試出某格牌 pick -> drop -> home (例: t 5)
  [v 排號]       : 到拍照點拍照 + Gemini 辨識該排 (例: v 1)
  [v all]        : 完整手牌辨識流程 (第一排 -> 第二排 -> 回初始點)
  [v p]          : Gemini 辨識出牌區
  [snap]         : 兩顆鏡頭各存一張照片
  [clamp open/close] : 排夾開 / 關 (也可 clamp 45 45 直接給 J7 J8 角度)
  [check]        : ESP32 自我測試 (確認收到指令會動作、緊急停止有效)
  [cams]         : 列出可用的鏡頭編號 (目前設定: 手牌 {HAND_CAMERA_INDEX}, 出牌 {PLAY_CAMERA_INDEX})
  其他
  [s]            : 緊急停止 (播放中也可以輸入)
  [r]            : 解除停止 / 回到即時連動 (⚠️ 手臂會移向示範臂姿勢)
  [exit]         : 離開
  手牌分排: {', '.join(f"{z['label']}={z['pose']} 格子{zone_slots(i)[0]}~{zone_slots(i)[-1]}" for i, z in enumerate(HAND_ZONES))}
=======================================================
"""


def main():
    robot = RobotArm(COM_PORT)
    preview = Preview(robot)
    print(HELP)

    while True:
        try:
            cmd_input = input(">> ").strip()
        except (KeyboardInterrupt, EOFError):
            break
        if not cmd_input:
            continue
        parts = cmd_input.split(maxsplit=1)
        op = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else None

        if op in ('s', 'stop'):
            robot.emergency_stop()
        elif op in ('exit', 'quit'):
            break
        elif robot.busy:
            print("⚠️ 手臂播放中，只能輸入 s 緊急停止")
        elif op in ('r', 'run'):
            robot.live()
            print("已回到即時連動模式")
        elif op == 'h':
            angles = robot.set_home()
            if angles:
                print(f"🏠 初始點已設定: {angles}")
        elif op == 'c':
            if arg and arg.isdigit() and 1 <= int(arg) <= len(HAND_ZONES):
                pose = HAND_ZONES[int(arg) - 1]['pose']
                angles = robot.save_pose(pose)
                if angles:
                    print(f"📷 {pose} 已設定: {angles}")
            else:
                print(f"⚠️ 用法: c 1~{len(HAND_ZONES)}")
        elif op == 'home':
            if robot.has_action(HOME):
                robot.run_sequence([HOME], return_home=False)
            else:
                print("⚠️ 尚未設定初始點，請先輸入 h")
        elif op == 'go':
            if arg and arg.isdigit() and 1 <= int(arg) <= len(HAND_ZONES):
                pose = HAND_ZONES[int(arg) - 1]['pose']
                if robot.has_action(pose):
                    robot.run_sequence([pose], return_home=False)
                else:
                    print(f"❌ 尚未設定 {pose}")
            else:
                print(f"⚠️ 用法: go 1~{len(HAND_ZONES)}")
        elif op == 'b':
            batch_record(robot, preview)
        elif op == '1':
            if arg:
                record_once(robot, preview, arg)
            else:
                print("⚠️ 請指定動作名稱，例如: 1 pick_05")
        elif op == '2':
            if arg and robot.has_action(arg):
                os.remove(robot.action_path(arg))
                print(f"🗑️ 已刪除: {arg}")
            else:
                print(f"❌ 找不到動作: {arg}")
        elif op == '3':
            list_actions(robot)
        elif op == '4':
            if arg and robot.has_action(arg):
                robot.run_sequence([arg], on_done=lambda ok: print(f"✅ {arg} 播放完成，已回初始點" if ok else "⚠️ 播放中斷"))
            else:
                print(f"❌ 找不到動作: {arg}")
        elif op == 't':
            if arg and arg.isdigit() and 1 <= int(arg) <= NUM_SLOTS:
                test_slot(robot, int(arg))
            else:
                print(f"⚠️ 請輸入格號 1~{NUM_SLOTS}，例如: t 5")
        elif op == 'v':
            test_vision(robot, preview, (arg or '').lower())
        elif op == 'snap':
            for cam, tag in ((preview.hand_cam, 'hand'), (preview.play_cam, 'play')):
                frame = cam.read()
                if frame is not None:
                    print(f"📸 {save_snapshot(frame, tag)}")
        elif op == 'clamp':
            if arg == 'open':
                robot.open_clamps()
            elif arg == 'close':
                robot.close_clamps()
            elif arg and len(arg.split()) == 2 and all(x.isdigit() for x in arg.split()):
                a7, a8 = map(int, arg.split())
                if robot.set_clamps([a7, a8]):
                    print(f"[排夾] J7={a7} J8={a8}")
            else:
                print(f"⚠️ 用法: clamp open / clamp close / clamp 角度7 角度8   (目前 {robot.clamp_angles})")
        elif op == 'check':
            print("🔧 ESP32 自我測試 (底座 J1 會轉 5° 再轉回，結束後回到跟隨示範臂)")
            print("✅ 全部通過" if robot.self_test() else "❌ 有項目沒通過")
        elif op == 'cams':
            used = {i for i, c in ((HAND_CAMERA_INDEX, preview.hand_cam), (PLAY_CAMERA_INDEX, preview.play_cam)) if c.ok}
            for i, info in probe_cameras(skip=used):
                print(f"   鏡頭 {i}: {info}")
        else:
            print("⚠️ 未知指令！")
            print(HELP)

    preview.close()


if __name__ == "__main__":
    main()
