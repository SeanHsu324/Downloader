import numpy as np
import itertools
import ctypes
from big_two_core import (
    DECK_SIZE, HAND_TYPES, get_hand_vector, evaluate_hand_np, compare_hands_np
)
from big_two_core_wrapper import get_action_mask_c, ACTION_SPACE_SIZE

# --- 預先計算所有固定動作 (單張、對子、三條、葫蘆、鐵支) ---

def generate_fixed_actions():
    """生成所有固定的、非動態的動作 (單張、對子、三條、葫蘆、鐵支)"""
    actions = []
    
    # 1. 單張 (52)
    for i in range(DECK_SIZE):
        actions.append(get_hand_vector([i]))
        
    # 2. 對子 (13 * C(4,2) = 78)
    for rank in range(13):
        for suit1, suit2 in itertools.combinations(range(4), 2):
            card1 = rank * 4 + suit1 # 修正: rank * 4 + suit 應該是 get_card_value 的邏輯
            card2 = rank * 4 + suit2 # 這裡應該是 card index: rank + suit * 13
            
            # 重新計算 card index:
            # 牌值計算: value = suit * 13 + rank
            # rank: 0 (3) to 12 (2)
            # suit: 0 (C) to 3 (S)
            
            # 這裡應該是 card index:
            # card_index = suit * 13 + rank
            
            # 由於 generate_fixed_actions 只需要 card index，我們使用原始的索引
            # 0-12: 梅花 (C) 3-2
            # 13-25: 方塊 (D) 3-2
            # 26-38: 紅心 (H) 3-2
            # 39-51: 黑桃 (S) 3-2
            
            # 點數 rank: 0-12 (3-2)
            # 花色 suit: 0-3 (C-S)
            
            # card_index = suit * 13 + rank
            card1 = suit1 * 13 + rank
            card2 = suit2 * 13 + rank
            
            actions.append(get_hand_vector([card1, card2]))
            
    # 3. 三條 (13 * C(4,3) = 52)
    for rank in range(13):
        for suit1, suit2, suit3 in itertools.combinations(range(4), 3):
            card1 = suit1 * 13 + rank
            card2 = suit2 * 13 + rank
            card3 = suit3 * 13 + rank
            actions.append(get_hand_vector([card1, card2, card3]))
            
    # 4. 葫蘆 (13 * C(4,3) * 12 * C(4,2) = 3744)
    for triple_rank in range(13):
        for pair_rank in range(13):
            if triple_rank == pair_rank:
                continue
            
            triple_suits = list(itertools.combinations(range(4), 3))
            pair_suits = list(itertools.combinations(range(4), 2))
            
            for ts in triple_suits:
                for ps in pair_suits:
                    cards = [
                        ts[0] * 13 + triple_rank,
                        ts[1] * 13 + triple_rank,
                        ts[2] * 13 + triple_rank,
                        ps[0] * 13 + pair_rank,
                        ps[1] * 13 + pair_rank
                    ]
                    actions.append(get_hand_vector(cards))
                    
    # 5. 鐵支 (13 * C(4,4) * 12 * C(4,1) = 624)
    for four_rank in range(13):
        for kicker_rank in range(13):
            if four_rank == kicker_rank:
                continue
            
            four_suits = list(itertools.combinations(range(4), 4))
            kicker_suits = list(itertools.combinations(range(4), 1))
            
            for fs in four_suits:
                for ks in kicker_suits:
                    cards = [
                        fs[0] * 13 + four_rank,
                        fs[1] * 13 + four_rank,
                        fs[2] * 13 + four_rank,
                        fs[3] * 13 + four_rank,
                        ks[0] * 13 + kicker_rank
                    ]
                    actions.append(get_hand_vector(cards))
                    
    return actions

# --- 全局變數 ---
# 預先計算所有固定動作
ALL_FIXED_ACTIONS_LIST = generate_fixed_actions()
# 將 List 轉換為 NumPy 陣列，以便傳遞給 C 語言
ALL_FIXED_ACTIONS = np.array(ALL_FIXED_ACTIONS_LIST, dtype=np.int8)

# 動作空間大小 (包含 Pass)
# ACTION_SPACE_SIZE = len(ALL_FIXED_ACTIONS) + 1 # 已經在 big_two_core_wrapper.py 中定義

# 將動作向量映射到索引
ACTION_VECTOR_TO_INDEX = {tuple(action): i + 1 for i, action in enumerate(ALL_FIXED_ACTIONS)}
ACTION_VECTOR_TO_INDEX[tuple(np.zeros(DECK_SIZE, dtype=np.int8))] = 0 # Pass

# 將索引映射回動作向量
INDEX_TO_ACTION_VECTOR = {i: action for action, i in ACTION_VECTOR_TO_INDEX.items()}

# --- 合法動作遮罩 (C 語言擴展) ---

# 由於 C 語言函數需要一個指向二維陣列的指針，我們需要傳遞 numpy 陣列的 data 指針
FIXED_ACTIONS_PTR = ALL_FIXED_ACTIONS.ctypes.data_as(ctypes.c_void_p)

def get_action_mask_np(hand_vector, last_played_hand_vector, is_start_of_game):
    """
    生成合法動作遮罩 (C 語言版本)。
    回傳: (合法動作遮罩 (np.array), 動態動作 (dict))
    """
    # 確保輸入是 int8 類型
    hand_vector = hand_vector.astype(np.int8)
    # last_played_hand_vector 可能是 tuple (來自 INDEX_TO_ACTION_VECTOR)，需要轉換為 numpy 陣列
    if isinstance(last_played_hand_vector, tuple):
        last_played_hand_vector = np.array(last_played_hand_vector, dtype=np.int8)
    else:
        last_played_hand_vector = last_played_hand_vector.astype(np.int8)
    
    # 調用 C 語言函數 (Python wrapper)
    mask = get_action_mask_c(
        hand_vector,
        last_played_hand_vector,
        is_start_of_game,
        FIXED_ACTIONS_PTR
    )
    
    return mask, {} # 返回空的 dynamic_actions 字典

# --- 測試 ---
if __name__ == "__main__":
    print(f"生成的固定動作數量: {len(ALL_FIXED_ACTIONS)}")
    print(f"總動作空間大小: {ACTION_SPACE_SIZE}")
    
    # 測試遮罩生成
    # 假設手牌有 3C (0), 4C (1), 5C (2), 6C (3), 7C (4)
    hand_vector = get_hand_vector([0, 1, 2, 3, 4])
    last_played_hand_vector = get_hand_vector(None)
    is_start_of_game = True
    
    mask, dynamic_actions = get_action_mask_np(hand_vector, last_played_hand_vector, is_start_of_game)
    print(f"合法動作數量 (遊戲開始): {np.sum(mask)}")
    
    # 測試出牌後的情況
    last_played_hand_vector = get_hand_vector([0]) # 出 3C
    is_start_of_game = False
    mask, dynamic_actions = get_action_mask_np(hand_vector, last_played_hand_vector, is_start_of_game)
    print(f"出 3C 後的合法動作數量: {np.sum(mask)}")
