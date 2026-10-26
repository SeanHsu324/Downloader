import ctypes
import numpy as np
import os

# 定義 C 語言結構和類型
DECK_SIZE = 52
ACTION_SPACE_SIZE = 4551

class HandEvaluation(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("value", ctypes.c_int)
    ]

# 載入共享庫
try:
    _lib = ctypes.CDLL(os.path.join(os.path.dirname(__file__), "big_two_c_lib.dll"))
except OSError:
    # 如果找不到，嘗試從當前目錄載入
    _lib = ctypes.CDLL(".big_two_c_lib.dll")

# --- 函數接口定義 ---

# 1. evaluate_hand_c
_lib.evaluate_hand_c.argtypes = [np.ctypeslib.ndpointer(dtype=np.int8, shape=(DECK_SIZE,))]
_lib.evaluate_hand_c.restype = HandEvaluation

def evaluate_hand_c(hand_vector: np.ndarray) -> HandEvaluation:
    """評估一手牌的牌型和大小 (C 語言實現)"""
    return _lib.evaluate_hand_c(hand_vector)

# 2. compare_hands_c
_lib.compare_hands_c.argtypes = [
    np.ctypeslib.ndpointer(dtype=np.int8, shape=(DECK_SIZE,)),
    np.ctypeslib.ndpointer(dtype=np.int8, shape=(DECK_SIZE,))
]
_lib.compare_hands_c.restype = ctypes.c_int

def compare_hands_c(hand1_vector: np.ndarray, hand2_vector: np.ndarray) -> int:
    """比較兩手牌的大小 (C 語言實現)"""
    return _lib.compare_hands_c(hand1_vector, hand2_vector)

# 3. get_action_mask_c
# 由於 fixed_actions 是一個二維陣列，我們需要一個特殊的指針類型
FixedActionsArray = ctypes.c_int8 * DECK_SIZE
# FixedActionsPtr = ctypes.POINTER(FixedActionsArray)

_lib.get_action_mask_c.argtypes = [
    np.ctypeslib.ndpointer(dtype=np.int8, shape=(DECK_SIZE,)), # hand_vector
    np.ctypeslib.ndpointer(dtype=np.int8, shape=(DECK_SIZE,)), # last_played_hand_vector
    ctypes.c_int, # is_start_of_game
    ctypes.c_void_p, # fixed_actions (使用 void_p 傳遞 numpy 陣列的 data 指針)
    np.ctypeslib.ndpointer(dtype=np.int8, shape=(ACTION_SPACE_SIZE,), flags='W') # mask (輸出)
]
_lib.get_action_mask_c.restype = None
def get_action_mask_c(
    hand_vector: np.ndarray,
    last_played_hand_vector: np.ndarray,
    is_start_of_game: bool,
    fixed_actions_ptr
) -> np.ndarray:
    """
    生成合法動作遮罩 (C 語言實現)。
    
    Args:
        hand_vector: 當前玩家的手牌向量 (52,).
        last_played_hand_vector: 最後出的牌向量 (52,).
        is_start_of_game: 是否為遊戲開始.
        fixed_actions_ptr: 預先計算好的固定動作的 data 指針.
        
    Returns:
        合法動作遮罩 (4551,).
    """
    mask = np.zeros(ACTION_SPACE_SIZE, dtype=np.int8)
    
    _lib.get_action_mask_c(
        hand_vector,
        last_played_hand_vector,
        int(is_start_of_game),
        fixed_actions_ptr,
        mask
    )
    
    return mask

# 為了測試，我們需要一個簡單的測試函數
def test_c_core():
    # 測試 evaluate_hand_c
    hand_vector = np.zeros(DECK_SIZE, dtype=np.int8)
    hand_vector[0] = 1 # 3C
    eval_result = evaluate_hand_c(hand_vector)
    # print(f"3C Eval: Type={eval_result.type}, Value={eval_result.value}")
    
    # 測試 compare_hands_c
    hand1 = np.zeros(DECK_SIZE, dtype=np.int8)
    hand1[51] = 1 # 2S
    hand2 = np.zeros(DECK_SIZE, dtype=np.int8)
    hand2[50] = 1 # 2H
    compare_result = compare_hands_c(hand1, hand2)
    # print(f"2S vs 2H: {compare_result}")
    
    # 測試 get_action_mask_c (需要 fixed_actions)
    # 由於 fixed_actions 是一個巨大的陣列，我們不能在這裡定義它
    # 我們將在 action_space.py 中處理這個問題
    
    return True

if __name__ == '__main__':
    print(f"C 核心庫載入成功: {_lib}")
    test_c_core()
